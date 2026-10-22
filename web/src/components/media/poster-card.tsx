import { AspectRatio, Box, Card, Center, Group, Stack, Text, UnstyledButton } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import {
  IconCalendar,
  IconCheck,
  IconHeart,
  IconHeartFilled,
  IconStar,
  IconUser,
} from "@tabler/icons-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useState, type MouseEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  batchMetadataUserTagsMutation,
  createUserTagsMutation,
  listFacetsQueryKey,
  listMetadataQueryKey,
} from "@/client/@tanstack/react-query.gen";
import type { MetadataResponse, UserTagResponse } from "@/client/types.gen";
import { FilePhaseOverlay } from "@/components/media/file-phase-badges";
import { OverlayChip, OverlayChipLabel } from "@/components/media/overlay-chip";
import { ProxyImage } from "@/components/media/proxy-image";
import { VrOverlayChip } from "@/components/media/vr-badge";
import { extractErrorMessage } from "@/lib/api-error";
import { ageAtRelease } from "@/lib/format-birthday";
import { formatReleaseYearMonth } from "@/lib/format-release";
import { USER_TAG_FACET_LIST } from "@/lib/facets";
import { proxyImageUrl } from "@/lib/utils";

/** 海报快捷开关写入的用户标签名 (固定中文, 便于筛选). */
export const WATCHED_USER_TAG = "已播放";
export const FAVORITE_USER_TAG = "收藏";

interface PosterCardProps {
  item: MetadataResponse;
  /** 传入时按影片发行日标注演员当时年龄 (演员详情出演墙). */
  actorBirthday?: string | null;
}

function hasTag(tags: UserTagResponse[] | undefined, name: string): boolean {
  return (tags ?? []).some((tag) => tag.name === name);
}

/** 加载失败退化为番号占位块. */
export function PosterCard({ item, actorBirthday }: PosterCardProps) {
  const { t } = useTranslation(["metadata", "common"]);
  const queryClient = useQueryClient();
  const [errored, setErrored] = useState(false);
  const [optimisticTags, setOptimisticTags] = useState<UserTagResponse[] | null>(null);
  const serverKey = `${item.id}:${(item.user_tags ?? []).map((tag) => `${tag.id}:${tag.name}`).join(",")}`;
  const [syncedKey, setSyncedKey] = useState(serverKey);
  if (serverKey !== syncedKey) {
    setSyncedKey(serverKey);
    setOptimisticTags(null);
  }
  const tags = optimisticTags ?? item.user_tags ?? [];

  const posterUrl = proxyImageUrl(item.poster_url ?? item.poster_urls?.[0]);
  const showImage = posterUrl && !errored;
  const actors = item.actors ?? [];
  const actorsLabel = actors.length > 0 ? actors.join(" / ") : null;
  const releaseLabel = formatReleaseYearMonth(item.release);
  const ageThen = ageAtRelease(actorBirthday, item.release);

  const watched = hasTag(tags, WATCHED_USER_TAG);
  const favorite = hasTag(tags, FAVORITE_USER_TAG);

  const ensureTags = useMutation(createUserTagsMutation());
  const applyTags = useMutation(batchMetadataUserTagsMutation());
  const busy = ensureTags.isPending || applyTags.isPending;

  async function toggleMark(name: string, active: boolean, event: MouseEvent) {
    event.preventDefault();
    event.stopPropagation();
    if (busy || item.id <= 0) {
      return;
    }
    const previous = tags;
    const optimistic: UserTagResponse[] = active
      ? previous.filter((tag) => tag.name !== name)
      : [...previous.filter((tag) => tag.name !== name), { id: -1, name }];
    setOptimisticTags(optimistic);
    try {
      const ensured = await ensureTags.mutateAsync({ body: { names: [name] } });
      const tagId = ensured.items[0]?.id;
      if (tagId == null) {
        throw new Error("missing tag id");
      }
      void queryClient.invalidateQueries({ queryKey: listFacetsQueryKey(USER_TAG_FACET_LIST) });
      await applyTags.mutateAsync({
        body: {
          ids: [item.id],
          user_tag_ids: [tagId],
          action: active ? "detach" : "attach",
        },
      });
      setOptimisticTags(null);
      void queryClient.invalidateQueries({ queryKey: listMetadataQueryKey() });
    } catch (err) {
      setOptimisticTags(null);
      notifications.show({
        message: extractErrorMessage(err, t("common:toast.operationFailed")),
        color: "red",
      });
    }
  }

  return (
    <Link
      to="/meta/$metadataId"
      params={{ metadataId: String(item.id) }}
      style={{ textDecoration: "none", color: "inherit", display: "block" }}
    >
      <Card padding={0} radius="md" withBorder style={{ overflow: "hidden" }}>
        <Box pos="relative">
          <AspectRatio ratio={0.7}>
            {showImage ? (
              <ProxyImage
                src={posterUrl}
                alt={item.number}
                loading="lazy"
                referrerPolicy="no-referrer"
                style={{ display: "block" }}
                onError={() => setErrored(true)}
              />
            ) : (
              <Center bg="var(--mantine-color-default-hover)" h="100%">
                <Text size="sm" ff="monospace" c="dimmed" ta="center" px="xs">
                  {item.number}
                </Text>
              </Center>
            )}
          </AspectRatio>
          <FilePhaseOverlay
            phase={item.file_phase}
            bottomExtra={
              ageThen != null ? (
                <OverlayChip>
                  <IconUser size={12} color="var(--mantine-color-grape-3)" />
                  <OverlayChipLabel>{t("actors.ageShort", { age: ageThen })}</OverlayChipLabel>
                </OverlayChip>
              ) : undefined
            }
          />
          {/* 与评分同角成组: 左上角被相位水印 (马赛克标记) 占用, 单独放会与它重叠. */}
          {(item.vr || item.score != null) && (
            <Group pos="absolute" top={6} right={6} gap={4} wrap="nowrap">
              {item.vr && <VrOverlayChip />}
              {item.score != null && (
                <OverlayChip>
                  <IconStar
                    size={11}
                    color="var(--mantine-color-yellow-4)"
                    fill="var(--mantine-color-yellow-4)"
                  />
                  <OverlayChipLabel>{item.score.toFixed(1)}</OverlayChipLabel>
                </OverlayChip>
              )}
            </Group>
          )}
          {releaseLabel && (
            <Box pos="absolute" bottom={6} right={6}>
              <OverlayChip>
                <IconCalendar size={12} color="var(--mantine-color-cyan-3)" />
                <OverlayChipLabel ff="monospace" lts={0.3}>
                  {releaseLabel}
                </OverlayChipLabel>
              </OverlayChip>
            </Box>
          )}
        </Box>
        <Stack gap={4} p="xs">
          <Text size="sm" fw={600} ff="monospace" lineClamp={1}>
            {item.number}
          </Text>
          {item.title && (
            <Text size="xs" c="dimmed" lineClamp={2} title={item.title}>
              {item.title}
            </Text>
          )}
          <Group gap={5} wrap="nowrap" align="center" justify="space-between">
            {actorsLabel ? (
              <Group
                gap={5}
                wrap="nowrap"
                align="center"
                title={actorsLabel}
                style={{ minWidth: 0, flex: 1 }}
              >
                <Box
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                    width: 18,
                    height: 18,
                    borderRadius: "var(--mantine-radius-sm)",
                    background: "var(--mantine-color-grape-filled)",
                    color: "var(--mantine-color-white)",
                  }}
                >
                  <IconUser size={11} stroke={2.2} />
                </Box>
                <Text size="xs" fw={600} lineClamp={1} style={{ minWidth: 0 }}>
                  {actorsLabel}
                </Text>
              </Group>
            ) : (
              <Box style={{ flex: 1, minWidth: 0 }} />
            )}
            <Group gap={2} wrap="nowrap" align="center" style={{ flexShrink: 0 }}>
              <UnstyledButton
                onClick={(event) => void toggleMark(WATCHED_USER_TAG, watched, event)}
                aria-pressed={watched}
                aria-label={t("detail.markWatched")}
                title={t("detail.markWatched")}
                disabled={busy}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: 24,
                  height: 24,
                  borderRadius: "var(--mantine-radius-sm)",
                  color: watched ? "var(--mantine-color-teal-6)" : "var(--mantine-color-dimmed)",
                  flexShrink: 0,
                }}
              >
                <IconCheck size={14} stroke={2.4} />
              </UnstyledButton>
              <UnstyledButton
                onClick={(event) => void toggleMark(FAVORITE_USER_TAG, favorite, event)}
                aria-pressed={favorite}
                aria-label={t("detail.markFavorite")}
                title={t("detail.markFavorite")}
                disabled={busy}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: 24,
                  height: 24,
                  borderRadius: "var(--mantine-radius-sm)",
                  color: favorite ? "var(--mantine-color-pink-6)" : "var(--mantine-color-dimmed)",
                  flexShrink: 0,
                }}
              >
                {favorite ? <IconHeartFilled size={14} /> : <IconHeart size={14} />}
              </UnstyledButton>
            </Group>
          </Group>
        </Stack>
      </Card>
    </Link>
  );
}
