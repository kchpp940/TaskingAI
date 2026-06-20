import { formatTimestamp } from '@/utils/util';

export const formatDateTime = (timestamp: number): string => {
  if (!timestamp) return '';
  return formatTimestamp(timestamp);
};

export const safeGet = <T, K extends keyof T>(obj: T | undefined | null, key: K, defaultValue: T[K]): T[K] => {
  if (obj == null) return defaultValue;
  const value = obj[key];
  return value == null ? defaultValue : value;
};

export const safeString = (value: string | undefined | null, defaultValue: string = ''): string => {
  return value == null || value === '' ? defaultValue : value;
};

export const safeNumber = (value: number | undefined | null, defaultValue: number = 0): number => {
  return value == null || isNaN(value) ? defaultValue : value;
};

export const safeArray = <T>(value: T[] | undefined | null, defaultValue: T[] = []): T[] => {
  return Array.isArray(value) ? value : defaultValue;
};

export const safeObject = <T extends Record<string, any>>(
  value: T | undefined | null,
  defaultValue: T = {} as T,
): T => {
  return value && typeof value === 'object' ? value : defaultValue;
};

export const parseJsonSafe = <T>(jsonString: string | undefined | null, defaultValue: T): T => {
  if (!jsonString) return defaultValue;
  try {
    return JSON.parse(jsonString) as T;
  } catch {
    return defaultValue;
  }
};

export const withTableKey = <T extends { id: string }>(item: T): T & { key: string } => ({
  ...item,
  key: item.id,
});
