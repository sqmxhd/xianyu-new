import dayjs, { type Dayjs } from "dayjs";
import timezone from "dayjs/plugin/timezone";
import utc from "dayjs/plugin/utc";

dayjs.extend(utc);
dayjs.extend(timezone);

export const DISPLAY_TIME_ZONE = "Asia/Shanghai";

const explicitTimezonePattern = /(?:z|[+-]\d{2}:?\d{2})$/i;

/**
 * API datetimes are UTC RFC 3339 values. Older responses omitted the UTC
 * suffix, so timezone-less values are deliberately interpreted as UTC too.
 */
export function parseApiTime(value?: string | null): Dayjs | null {
  if (!value) {
    return null;
  }
  const normalized = value.trim();
  if (!normalized) {
    return null;
  }
  const parsed = explicitTimezonePattern.test(normalized)
    ? dayjs(normalized)
    : dayjs.utc(normalized);
  return parsed.isValid() ? parsed : null;
}

export function apiTimeToEpochMs(value?: string | null): number {
  return parseApiTime(value)?.valueOf() ?? Number.NaN;
}

export function formatBeijingTime(value?: string | null): string {
  const parsed = parseApiTime(value);
  if (!parsed) {
    return "-";
  }
  return parsed.tz(DISPLAY_TIME_ZONE).format("YYYY-MM-DD HH:mm:ss");
}

export function formatCompactBeijingTime(value?: string | null): string {
  const parsed = parseApiTime(value);
  if (!parsed) {
    return "-";
  }
  return parsed.tz(DISPLAY_TIME_ZONE).format("MM-DD HH:mm");
}
