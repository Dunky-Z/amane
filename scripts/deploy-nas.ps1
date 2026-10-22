#requires -Version 7.0
[CmdletBinding()]
param(
    [string]$NasHost = 'NAS',
    [string]$NasDirectory = '/root/sharedfolder/docker-compose',
    [string]$DockerContext = 'desktop-linux',
    [string]$Image,
    [string]$BuildProxy = 'http://192.168.31.220:7890',
    [switch]$BuildOnly,
    [switch]$SkipBuild,
    [switch]$CheckOnly,
    [switch]$Rollback
)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$timer = [Diagnostics.Stopwatch]::StartNew()

function Invoke-Native {
    param([string]$Command, [string[]]$Arguments)
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Command 执行失败, 退出码 $LASTEXITCODE" }
}

function Get-NativeOutput {
    param([string]$Command, [string[]]$Arguments)
    $result = & $Command @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Command 执行失败, 退出码 $LASTEXITCODE" }
    return ($result -join "`n")
}

if (@($BuildOnly, $CheckOnly, $Rollback).Where({ $_ }).Count -gt 1) {
    throw 'BuildOnly、CheckOnly 与 Rollback 不能同时使用'
}
if ($SkipBuild -and ($BuildOnly -or $CheckOnly -or $Rollback -or !$Image)) {
    throw 'SkipBuild 仅用于部署, 且必须指定 Image'
}
if ($NasHost -notmatch '^[a-zA-Z0-9_@.-]+$' -or $NasHost.StartsWith('-')) {
    throw 'SSH 主机名称无效'
}
if ($NasDirectory -notmatch '^/[a-zA-Z0-9_./-]+$' -or $NasDirectory.Contains('..')) {
    throw 'NAS 目录必须为不含空格与 .. 的绝对路径'
}
if ($Image -and $Image -notmatch '^amane-local:[a-zA-Z0-9_][a-zA-Z0-9_.-]{0,127}$') {
    throw 'Image 必须为 amane-local:<标签>'
}

$revision = Get-NativeOutput git @('-C', $root, 'rev-parse', 'HEAD')
$versionMatch = Select-String -LiteralPath (Join-Path $root 'pyproject.toml') -Pattern '^version = "([^"]+)"$'
$version = $versionMatch.Matches[0].Groups[1].Value
if (!$Image) { $Image = "amane-local:$version-$($revision.Substring(0, 8))" }
$release = (Get-Date -Format 'yyyyMMdd-HHmmss-fff') + '-' + $revision.Substring(0, 8)
$work = Join-Path ([IO.Path]::GetTempPath()) "amane-nas-$release"
$archive = Join-Path $work 'image.tar'
$sshOptions = @('-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', '-o', 'ServerAliveInterval=15')
$scpOptions = @('-O', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10')
$dockerArgs = @('--context', $DockerContext)

try {
    if (!$CheckOnly -and !$Rollback) {
        $context = (Get-NativeOutput docker @('context', 'inspect', $DockerContext)) | ConvertFrom-Json
        if ($context[0].Endpoints.docker.Host -notlike 'npipe://*') {
            throw '构建和导出必须使用本机 Windows Docker 引擎'
        }
        if (!$SkipBuild) {
            Invoke-Native docker ($dockerArgs + @(
                'build', '--platform', 'linux/amd64', '--provenance=false',
                '--build-arg', "HTTP_PROXY=$BuildProxy", '--build-arg', "HTTPS_PROXY=$BuildProxy",
                '--label', "org.opencontainers.image.version=$version",
                '--label', "org.opencontainers.image.revision=$revision",
                '-t', $Image, '-t', 'amane-local:latest', $root
            ))
        }
        $info = (Get-NativeOutput docker ($dockerArgs + @('image', 'inspect', $Image))) | ConvertFrom-Json
        if ($info[0].Os -ne 'linux' -or $info[0].Architecture -ne 'amd64') {
            throw "镜像架构必须为 linux/amd64: $Image"
        }
        $imageId = $info[0].Id
        Write-Host "本机镜像: $Image ($imageId)"
        if ($BuildOnly) { return }
    }

    $remote = "$NasDirectory/amane/.deploy/incoming/$release"
    Invoke-Native ssh ($sshOptions + @($NasHost, "umask 077; mkdir -p '$remote'"))
    Invoke-Native scp ($scpOptions + @((Join-Path $PSScriptRoot 'deploy-nas.sh'), "${NasHost}:$remote/deploy-nas.sh"))
    $helper = "bash '$remote/deploy-nas.sh'"
    $checkMode = if ($Rollback) { 'allow-unhealthy' } else { '-' }
    $before = (Get-NativeOutput ssh ($sshOptions + @(
        $NasHost, "$helper check '$NasDirectory' '$release' '$checkMode'"
    ))) | ConvertFrom-Json
    Write-Host "NAS: $($before.host), 当前镜像 $($before.image), 版本 $($before.version)"
    if ($CheckOnly) { return }
    if ($Rollback) {
        Invoke-Native ssh ($sshOptions + @($NasHost, "$helper rollback '$NasDirectory' '$release'"))
        return
    }

    $checksum = '-'
    if ($before.image -ne $imageId) {
        New-Item -ItemType Directory -Force -Path $work | Out-Null
        # PowerShell 的文本管道不能用于传输 Docker 二进制归档.
        Invoke-Native docker ($dockerArgs + @('image', 'save', '-o', $archive, $Image))
        $checksum = (Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash.ToLowerInvariant()
        Write-Host ("局域网传输: {0:N1} MiB" -f ((Get-Item -LiteralPath $archive).Length / 1MB))
        Invoke-Native scp ($scpOptions + @($archive, "${NasHost}:$remote/image.tar"))
    }
    Invoke-Native ssh ($sshOptions + @(
        $NasHost, "$helper deploy '$NasDirectory' '$release' '$imageId' '$checksum'"
    ))
} finally {
    if (Test-Path -LiteralPath $archive) { Remove-Item -LiteralPath $archive -Force }
    Write-Host ("耗时: {0:N1} 秒" -f $timer.Elapsed.TotalSeconds)
}
