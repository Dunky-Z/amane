#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

action=${1:?缺少操作}
directory=${2:?缺少 Compose 目录}
release=${3:?缺少部署标识}
target=${4:-}
checksum=${5:-}
[[ $action =~ ^(check|deploy|rollback)$ ]] || { echo '操作无效' >&2; exit 1; }
[[ $directory =~ ^/[a-zA-Z0-9_./-]+$ && $directory != *..* ]] || exit 1
[[ $release =~ ^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,100}$ ]] || exit 1
[[ $(hostname) == RISCX ]] || { echo '目标主机必须为 RISCX' >&2; exit 1; }
directory=$(readlink -f "$directory")
state="$directory/amane/.deploy"
incoming="$state/incoming/$release"
mkdir -p "$state/releases"
printf '*\n' > "$state/.gitignore"
exec 9> "$state/deploy.lock"
flock -n 9 || { echo '已有 Amane 部署正在执行' >&2; exit 1; }

compose() {
    docker compose --project-directory "$directory" -p docker-compose -f "$directory/docker-compose.yml" "$@"
}

image_version() {
    docker run --rm --network none --entrypoint python "$1" -c \
        'from importlib.metadata import version; print(version("amane"))'
}

db_revision() {
    # 容器无法启动时仍能读取数据库, 以便执行镜像回滚.
    docker run --rm --network none --volumes-from amane:ro --entrypoint python "$previous" -c \
        'import sqlite3; c=sqlite3.connect("file:/data/amane.db?mode=ro",uri=True); print(c.execute("select version_num from alembic_version").fetchone()[0])'
}

healthy() {
    [[ $(docker inspect amane --format '{{.Image}} {{.State.Running}}') == "$1 true" ]] || return 1
    curl --noproxy '*' -fsS --max-time 5 http://127.0.0.1:8800/api/health |
        python3 -c 'import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get("status")=="ok" and d.get("version")==sys.argv[1] else 1)' "$2" || return 1
    curl --noproxy '*' -fsS --max-time 5 -o /dev/null http://127.0.0.1:8800/ || return 1
    [[ $(docker inspect amane --format '{{.State.Health.Status}}') == healthy ]]
}

wait_healthy() {
    local deadline=$((SECONDS + 150))
    while (( SECONDS < deadline )); do
        if healthy "$1" "$2" 2>/dev/null; then return 0; fi
        sleep 2
    done
    echo '容器在 150 秒内未通过镜像、版本、API 与页面检查' >&2
    return 1
}

# 只接受主编排所属的生产服务; 显式指定主文件时不能遗漏额外的 override.
details=$(docker inspect amane --format '{{.Image}}|{{index .Config.Labels "com.docker.compose.project"}}|{{index .Config.Labels "com.docker.compose.service"}}|{{index .Config.Labels "com.docker.compose.project.working_dir"}}|{{index .Config.Labels "com.docker.compose.project.config_files"}}')
IFS='|' read -r previous project service working_dir config_files <<< "$details"
[[ $project == docker-compose && $service == amane ]] || { echo '生产容器归属不匹配' >&2; exit 1; }
[[ $(readlink -f "$working_dir") == "$directory" && $(readlink -f "$config_files") == "$directory/docker-compose.yml" ]] || {
    echo '生产 Compose 文件与部署目录不匹配' >&2; exit 1;
}
config_image=$(compose config --format json | python3 -c 'import json,sys; print(json.load(sys.stdin)["services"]["amane"]["image"])')
[[ $config_image == amane-local:latest ]] || { echo '生产镜像必须为 amane-local:latest' >&2; exit 1; }
previous_version=$(image_version "$previous")
if [[ $action == check ]]; then
    if [[ $target != allow-unhealthy ]]; then
        healthy "$previous" "$previous_version" || { echo '生产基线未通过健康检查' >&2; exit 1; }
    fi
    printf '{"host":"RISCX","image":"%s","version":"%s"}\n' "$previous" "$previous_version"
    exit 0
fi

if [[ $action == rollback ]]; then
    current=$(cat "$state/current")
    [[ $current =~ ^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,100}$ ]] || exit 1
    target=$(cat "$state/releases/$current/previous-image")
else
    [[ $target =~ ^sha256:[a-f0-9]{64}$ ]] || exit 1
    if [[ $previous == "$target" ]]; then
        healthy "$previous" "$previous_version"
        echo '镜像未变化, 已跳过传输与容器重建'
        exit 0
    fi
    healthy "$previous" "$previous_version" || { echo '生产基线未通过健康检查' >&2; exit 1; }
    [[ $checksum =~ ^[a-f0-9]{64}$ ]] || exit 1
    printf '%s  %s\n' "$checksum" "$incoming/image.tar" | sha256sum -c -
    docker load -i "$incoming/image.tar"
    rm -- "$incoming/image.tar"
fi
[[ $target =~ ^sha256:[a-f0-9]{64}$ ]] || exit 1
[[ $(docker image inspect "$target" --format '{{.Os}}/{{.Architecture}}') == linux/amd64 ]] || exit 1
target_version=$(image_version "$target")
target_head=$(docker run --rm --network none --entrypoint python "$target" -c \
    'from alembic.config import Config; from alembic.script import ScriptDirectory; print(ScriptDirectory.from_config(Config("/app/alembic.ini")).get_current_head())')
baseline_revision=$(db_revision)
[[ $target_head == "$baseline_revision" ]] || {
    echo "目标迁移版本 $target_head 与生产 $baseline_revision 不同, 需要单独安排数据库迁移" >&2; exit 1;
}

record="$state/releases/$release"
mkdir "$record"
printf '%s\n' "$previous" > "$record/previous-image"
printf '%s\n' "$target" > "$record/target-image"
printf '%s\n' "$baseline_revision" > "$record/db-revision"
printf '%s\n' "$action" > "$record/action"
date -Iseconds > "$record/started-at"

status() {
    printf '%s\n' "$1" > "$record/status.tmp"
    mv -- "$record/status.tmp" "$record/status"
}

# SQLite online backup 包含 WAL 中已提交的数据, 不能直接复制 amane.db.
docker exec amane python -c \
    'import sqlite3,sys; from pathlib import Path; p=Path("/data/.nas-deploy-backups")/sys.argv[1]; p.mkdir(parents=True,exist_ok=False); src=sqlite3.connect("file:/data/amane.db?mode=ro",uri=True); dst=sqlite3.connect(str(p/"amane.db")); src.backup(dst); dst.close(); src.close()' "$release"
docker tag "$previous" "amane-local:before-$release"
status applying

recover() {
    trap - ERR HUP INT TERM
    set +e
    echo '部署失败, 正在恢复原镜像' >&2
    if [[ $(db_revision) == "$baseline_revision" ]] &&
        docker tag "$previous" amane-local:latest &&
        compose up -d --no-deps --no-build --pull never --force-recreate amane &&
        wait_healthy "$previous" "$previous_version"; then
        status rolled-back
    else
        status rollback-failed
        echo "自动回滚失败, 检查 $record; 数据库备份位于 /data/.nas-deploy-backups/$release" >&2
    fi
    exit 1
}
trap recover ERR HUP INT TERM
docker tag "$target" amane-local:latest
compose up -d --no-deps --no-build --pull never --force-recreate amane
wait_healthy "$target" "$target_version"
status healthy
printf '%s\n' "$release" > "$state/current.tmp"
mv -- "$state/current.tmp" "$state/current"
trap - ERR HUP INT TERM
echo "部署完成: $target_version ($target), 记录: $record"
