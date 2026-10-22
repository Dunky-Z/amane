import { Group, NumberInput, Pagination } from "@mantine/core";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNarrowViewport } from "@/hooks/use-narrow-viewport";

interface PosterPaginationProps {
  page: number;
  totalPages: number;
  onChange: (page: number) => void;
}

/** 片库海报墙的翻页条. 窄屏收起两侧页码, 页码输入负责跳转. */
export function PosterPagination({ page, totalPages, onChange }: PosterPaginationProps) {
  const { t } = useTranslation("common");
  const narrow = useNarrowViewport("md");
  const [draft, setDraft] = useState(String(page));
  const [focused, setFocused] = useState(false);

  if (totalPages <= 1) return null;

  function commit(raw: string) {
    const trimmed = raw.trim();
    const value = Number(trimmed);
    if (!/^\d+$/.test(trimmed) || !Number.isInteger(value) || value < 1 || value > totalPages) {
      setDraft(String(page));
      return;
    }
    setDraft(String(value));
    if (value !== page) onChange(value);
  }

  return (
    <Group justify="center" gap="xs" wrap="wrap">
      <Pagination
        total={totalPages}
        value={Math.min(page, totalPages)}
        onChange={onChange}
        withEdges
        siblings={narrow ? 0 : 1}
        size={narrow ? "sm" : "md"}
      />
      <NumberInput
        aria-label={t("pagination.jumpTo")}
        value={focused ? draft : String(page)}
        onChange={(value) => setDraft(String(value))}
        onFocus={(event) => {
          setDraft(String(page));
          setFocused(true);
          event.currentTarget.select();
        }}
        onBlur={(event) => {
          setFocused(false);
          commit(event.currentTarget.value);
        }}
        onKeyDown={(event) => {
          if (event.key !== "Enter") return;
          commit(event.currentTarget.value);
          event.currentTarget.blur();
        }}
        min={1}
        max={totalPages}
        clampBehavior="strict"
        allowDecimal={false}
        allowNegative={false}
        hideControls
        w={72}
        size={narrow ? "sm" : "md"}
      />
    </Group>
  );
}
