import { Button, Group, Input, Textarea } from "@mantine/core";
import type { AnyFieldApi } from "@tanstack/react-form";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { FieldProps } from "../schema";
import { isNullable } from "../schema";
import type { TextJSONSchema } from "../schema/types";
import { useSchemaFormTranslate } from "../translate-context";
import { useFieldDomId } from "./dict-entry-form";
import { FieldChrome } from "./field-chrome";
import { fieldError } from "./field-error";

/**
 * Generic text input field. Also serves as the fallback for unrecognized schema types.
 * Accepts the broad SchemaFieldProps since it may receive composed or untyped schemas.
 *
 * `x-long` renders a taller textarea (rows=8) for long-form text (notes, logs,
 * body text) that benefits from more vertical space.
 *
 * The multiline branch must use `Textarea`: a bare `Input component="textarea"`
 * inherits Input's fixed height (`--input-size` = `--input-height`), so `rows`
 * has no effect and overflowing content only shows a scrollbar.
 */
export function TextField({
  name,
  label,
  description,
  schema,
  form,
  variant,
}: FieldProps<TextJSONSchema>) {
  const { t } = useTranslation("common");
  const id = useFieldDomId(name);
  const nullable = isNullable(schema);
  const multiline = schema["x-long"] === true;
  const onTranslate = useSchemaFormTranslate();
  const [translating, setTranslating] = useState(false);
  const canTranslate = schema["x-translate"] === true && onTranslate != null;
  const fieldName = name.split(".").pop() ?? name;

  return (
    <form.Field name={name}>
      {(field: AnyFieldApi) => (
        <FieldChrome
          variant={variant}
          htmlFor={id}
          label={label}
          description={description}
          error={fieldError(field)}
        >
          <Group gap="xs" wrap="nowrap" align={multiline ? "flex-start" : "center"}>
            {multiline ? (
              <Textarea
                id={id}
                rows={8}
                value={(field.state.value as string) ?? ""}
                onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) =>
                  field.handleChange(e.target.value || (nullable ? null : ""))
                }
                placeholder={nullable ? "(not set)" : undefined}
                style={{ flex: 1 }}
              />
            ) : (
              <Input
                id={id}
                value={(field.state.value as string) ?? ""}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                  field.handleChange(e.target.value || (nullable ? null : ""))
                }
                placeholder={nullable ? "(not set)" : undefined}
                style={{ flex: 1 }}
              />
            )}
            {canTranslate ? (
              typeof field.state.value === "string" && field.state.value.trim().length > 0 ? (
                <Button
                  type="button"
                  variant="outline"
                  size="compact-sm"
                  loading={translating}
                  onClick={async () => {
                    if (onTranslate == null) return;
                    const source = (field.state.value as string).trim();
                    if (!source) return;
                    setTranslating(true);
                    try {
                      const result = await onTranslate({ field: fieldName, text: source });
                      if (result?.text != null) {
                        field.handleChange(result.text);
                      }
                    } finally {
                      setTranslating(false);
                    }
                  }}
                >
                  {t("actions.translate")}
                </Button>
              ) : null
            ) : nullable && field.state.value != null ? (
              <Button type="button" variant="outline" size="compact-sm" onClick={() => field.handleChange(null)}>
                {t("actions.clear")}
              </Button>
            ) : null}
          </Group>
        </FieldChrome>
      )}
    </form.Field>
  );
}
