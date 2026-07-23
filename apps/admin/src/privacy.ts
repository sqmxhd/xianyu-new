export type PrivacyValueKind =
  | "name"
  | "identifier"
  | "phone"
  | "ipv4"
  | "ipv6"
  | "address"
  | "content"
  | "url";

function graphemes(value: string): string[] {
  const Segmenter = (Intl as typeof Intl & {
    Segmenter?: new (
      locale?: string,
      options?: { granularity: "grapheme" }
    ) => { segment(input: string): Iterable<{ segment: string }> };
  }).Segmenter;
  if (!Segmenter) return Array.from(value);
  return Array.from(new Segmenter("zh-CN", { granularity: "grapheme" }).segment(value), item => item.segment);
}

function containsHan(value: string): boolean {
  return /\p{Script=Han}/u.test(value);
}

export function maskName(value?: string | null): string {
  const normalized = value?.trim() ?? "";
  if (!normalized || normalized === "-") return normalized || "-";
  const parts = graphemes(normalized);
  if (containsHan(normalized)) {
    if (parts.length === 1) return "****";
    if (parts.length === 2) return `${parts[0]}****`;
    if (parts.length <= 4) return `${parts[0]}****${parts[parts.length - 1]}`;
    return `${parts.slice(0, 2).join("")}****${parts.slice(-2).join("")}`;
  }
  if (parts.length <= 2) return "****";
  if (parts.length <= 4) return `${parts[0]}****${parts[parts.length - 1]}`;
  if (parts.length <= 8) return `${parts.slice(0, 2).join("")}****${parts.slice(-2).join("")}`;
  return `${parts.slice(0, 4).join("")}****${parts.slice(-4).join("")}`;
}

export function maskIdentifier(value?: string | null): string {
  const normalized = value?.trim() ?? "";
  if (!normalized || normalized === "-") return normalized || "-";
  const parts = graphemes(normalized);
  if (parts.length <= 4) return parts.length <= 1 ? "****" : `${parts[0]}****`;
  if (parts.length <= 8) return `${parts.slice(0, 2).join("")}****${parts.slice(-2).join("")}`;
  return `${parts.slice(0, 4).join("")}****${parts.slice(-4).join("")}`;
}

export function maskPhone(value?: string | null): string {
  const normalized = value?.trim() ?? "";
  if (!normalized) return "-";
  return normalized.length >= 7
    ? `${normalized.slice(0, 3)}****${normalized.slice(-4)}`
    : maskIdentifier(normalized);
}

export function maskIPv4(value?: string | null): string {
  const normalized = value?.trim() ?? "";
  const parts = normalized.split(".");
  return parts.length === 4 ? `${parts[0]}.***.***.${parts[3]}` : maskIdentifier(normalized);
}

export function maskIPv6(value?: string | null): string {
  const normalized = value?.trim() ?? "";
  if (!normalized) return "-";
  const parts = normalized.split(":").filter(Boolean);
  return parts.length > 1
    ? `${parts[0]}:****:${parts[parts.length - 1]}`
    : maskIdentifier(normalized);
}

export function maskSensitive(
  value: string | number | null | undefined,
  enabled: boolean,
  kind: PrivacyValueKind = "name"
): string {
  const normalized = value == null ? "" : String(value);
  if (!enabled) return normalized;
  if (kind === "content") return normalized ? "内容已隐藏" : "";
  if (kind === "url") return normalized ? "链接已隐藏" : "";
  if (kind === "phone") return maskPhone(normalized);
  if (kind === "ipv4") return maskIPv4(normalized);
  if (kind === "ipv6") return maskIPv6(normalized);
  if (kind === "identifier") return maskIdentifier(normalized);
  if (kind === "address") return normalized ? "地址已隐藏" : "";
  return maskName(normalized);
}

export function privacyLocation(
  enabled: boolean,
  country?: string | null,
  province?: string | null,
  city?: string | null,
  extra?: string | null
): string {
  return [country, province, enabled ? null : city, enabled ? null : extra]
    .filter(Boolean)
    .join(" · ");
}
