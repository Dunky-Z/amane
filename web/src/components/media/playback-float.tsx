import { ActionIcon, Group, Text } from "@mantine/core";
import { IconGripVertical, IconX } from "@tabler/icons-react";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from "react";
import { useTranslation } from "react-i18next";

import { PlaybackPanel } from "@/components/media/playback-panel";
import type { SeekRequest } from "@/components/media/playback-player";

import classes from "./playback-float.module.css";

const DEFAULT_WIDTH = 720;
const DEFAULT_HEIGHT = 480;
const MIN_WIDTH = 360;
const MIN_HEIGHT = 280;

type DragState = {
  pointerId: number;
  startX: number;
  startY: number;
  originLeft: number;
  originTop: number;
};

type PanelGeom = {
  left: number;
  top: number;
  width: number;
  height: number;
};

/**
 * 页内可拖动、可改尺寸的播放浮层.
 *
 * 关闭时卸载面板以停播. 尺寸经 CSS `resize` 改; 标题栏拖动改位移.
 * 几何只在本组件会话内保留, 不 persist. `width`/`height` 首次打开写入后不再由 React
 * 覆盖, 否则会冲掉用户拖角改尺寸的结果.
 */
export function PlaybackFloat({
  opened,
  onClose,
  metadataId,
  title,
  seekRequest,
  onSeekHandled,
  onCanSeekChange,
}: {
  opened: boolean;
  onClose: () => void;
  metadataId: number;
  /** 浮层标题, 通常为番号. */
  title: string;
  seekRequest: SeekRequest | null;
  onSeekHandled: () => void;
  onCanSeekChange: (canSeek: boolean) => void;
}) {
  const { t } = useTranslation("metadata");
  const panelRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<DragState | null>(null);
  const [geom, setGeom] = useState<PanelGeom | null>(null);

  if (opened && geom == null) {
    const width = Math.min(DEFAULT_WIDTH, window.innerWidth - 32);
    const height = Math.min(DEFAULT_HEIGHT, window.innerHeight - 32);
    setGeom({
      left: Math.max(16, window.innerWidth - width - 24),
      top: Math.max(16, Math.round((window.innerHeight - height) / 5)),
      width,
      height,
    });
  }
  const hasGeom = geom != null;

  useEffect(() => {
    if (!opened) {
      return;
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [opened, onClose]);

  // 用户经 CSS resize 改尺寸后, 把结果同步回 state, 供拖动边界计算使用.
  useEffect(() => {
    if (!opened || !hasGeom) {
      return;
    }
    const panel = panelRef.current;
    if (panel == null) {
      return;
    }
    const observer = new ResizeObserver(() => {
      setGeom((prev) => {
        if (prev == null) {
          return prev;
        }
        const width = panel.offsetWidth;
        const height = panel.offsetHeight;
        if (width === prev.width && height === prev.height) {
          return prev;
        }
        return { ...prev, width, height };
      });
    });
    observer.observe(panel);
    return () => observer.disconnect();
  }, [opened, hasGeom]);

  const onPointerDown = useCallback((event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) {
      return;
    }
    const panel = panelRef.current;
    if (panel == null) {
      return;
    }
    const rect = panel.getBoundingClientRect();
    dragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originLeft: rect.left,
      originTop: rect.top,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  }, []);

  const onPointerMove = useCallback((event: ReactPointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current;
    if (drag == null || drag.pointerId !== event.pointerId) {
      return;
    }
    const panel = panelRef.current;
    if (panel == null) {
      return;
    }
    const width = panel.offsetWidth;
    const height = panel.offsetHeight;
    const nextLeft = drag.originLeft + (event.clientX - drag.startX);
    const nextTop = drag.originTop + (event.clientY - drag.startY);
    setGeom((prev) => {
      if (prev == null) {
        return prev;
      }
      return {
        ...prev,
        left: Math.min(Math.max(0, nextLeft), Math.max(0, window.innerWidth - width)),
        top: Math.min(Math.max(0, nextTop), Math.max(0, window.innerHeight - height)),
      };
    });
  }, []);

  const onPointerUp = useCallback((event: ReactPointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current;
    if (drag == null || drag.pointerId !== event.pointerId) {
      return;
    }
    dragRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }, []);

  if (!opened || geom == null) {
    return null;
  }

  return (
    <div
      ref={panelRef}
      className={classes.root}
      style={{
        left: geom.left,
        top: geom.top,
        width: geom.width,
        height: geom.height,
        minWidth: MIN_WIDTH,
        minHeight: MIN_HEIGHT,
      }}
      role="dialog"
      aria-modal="false"
      aria-label={t("detail.playback")}
    >
      <div
        className={classes.header}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        <Group gap={6} wrap="nowrap" style={{ flex: 1, minWidth: 0 }}>
          <IconGripVertical size={16} className={classes.grip} aria-hidden />
          <Text size="sm" fw={600} truncate="end">
            {title}
          </Text>
        </Group>
        <ActionIcon
          variant="subtle"
          color="gray"
          size="sm"
          aria-label={t("detail.playbackClose")}
          onClick={onClose}
          onPointerDown={(event) => event.stopPropagation()}
        >
          <IconX size={16} />
        </ActionIcon>
      </div>
      <div className={classes.body}>
        <PlaybackPanel
          metadataId={metadataId}
          seekRequest={seekRequest}
          onSeekHandled={onSeekHandled}
          onCanSeekChange={onCanSeekChange}
          autoScrollOnSeek={false}
        />
      </div>
    </div>
  );
}
