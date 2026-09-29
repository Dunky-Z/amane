import { Button, Checkbox, Group, Modal, Stack, Text } from "@mantine/core";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

export type MetadataDeleteChoice = {
  deleteFiles: boolean;
};

type PendingDelete = {
  title: string;
  message: string;
  resolve: (choice: MetadataDeleteChoice | null) => void;
};

type DeleteBridge = {
  open: (pending: PendingDelete) => void;
};

let bridge: DeleteBridge | null = null;

/** 删除元数据前的选项. 须在 MantineProvider 内挂载 `<MetadataDeleteDialogHost />`. */
export function confirmMetadataDelete(options: {
  title: string;
  message: string;
}): Promise<MetadataDeleteChoice | null> {
  return new Promise((resolve) => {
    if (bridge == null) {
      resolve(null);
      return;
    }
    bridge.open({ ...options, resolve });
  });
}

export function MetadataDeleteDialogHost() {
  const { t } = useTranslation(["metadata", "common"]);
  const [pending, setPending] = useState<PendingDelete | null>(null);
  const [deleteMetadata, setDeleteMetadata] = useState(true);
  const [deleteFiles, setDeleteFiles] = useState(false);

  useEffect(() => {
    bridge = {
      open: (next) => {
        setDeleteMetadata(true);
        setDeleteFiles(false);
        setPending((prev) => {
          prev?.resolve(null);
          return next;
        });
      },
    };
    return () => {
      bridge = null;
    };
  }, []);

  function close(choice: MetadataDeleteChoice | null) {
    setPending((prev) => {
      prev?.resolve(choice);
      return null;
    });
  }

  const canConfirm = deleteMetadata || deleteFiles;

  return (
    <Modal
      opened={pending != null}
      onClose={() => close(null)}
      title={pending?.title}
      centered
      size="sm"
      radius="md"
    >
      <Stack gap="md">
        <Text size="sm">{pending?.message}</Text>
        <Checkbox
          checked={deleteFiles || deleteMetadata}
          disabled={deleteFiles}
          onChange={(event) => setDeleteMetadata(event.currentTarget.checked)}
          label={t("deleteChoice.metadata")}
          description={t("deleteChoice.metadataHint")}
        />
        <Checkbox
          checked={deleteFiles}
          onChange={(event) => {
            const checked = event.currentTarget.checked;
            setDeleteFiles(checked);
            if (checked) setDeleteMetadata(true);
          }}
          label={t("deleteChoice.files")}
          description={t("deleteChoice.filesHint")}
        />
        <Group justify="flex-end" gap="sm">
          <Button variant="default" onClick={() => close(null)}>
            {t("common:actions.cancel")}
          </Button>
          <Button color="red" disabled={!canConfirm} onClick={() => close({ deleteFiles })}>
            {t("common:actions.delete")}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
