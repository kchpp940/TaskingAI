import { SearchParams } from './types';

export const buildPrefixFilter = (
  idFieldName: string,
  nameSearch?: string,
  idSearch?: string,
): Record<string, string> | undefined => {
  if (nameSearch) {
    return { name: nameSearch };
  }
  if (idSearch) {
    return { [idFieldName]: idSearch };
  }
  return undefined;
};

export const buildQueryString = (params: Record<string, any>): string => {
  const filtered = Object.entries(params)
    .filter(([, value]) => value !== undefined && value !== null && value !== '');

  if (filtered.length === 0) return '';

  return filtered
    .map(([key, value]) => {
      const encodedValue = typeof value === 'object' ? JSON.stringify(value) : String(value);
      return `${encodeURIComponent(key)}=${encodeURIComponent(encodedValue)}`;
    })
    .join('&');
};

export const buildListParams = (
  idFieldName: string,
  params: SearchParams & Record<string, any>,
): string => {
  const { name_search, id_search, ...rest } = params;
  const queryParams: Record<string, any> = { ...rest };

  const prefixFilter = buildPrefixFilter(idFieldName, name_search, id_search);
  if (prefixFilter) {
    queryParams.prefix_filter = prefixFilter;
  }

  return buildQueryString(queryParams);
};
