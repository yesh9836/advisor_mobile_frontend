export type QueryParamValue = string | number | boolean | null | undefined;

export const normalizeQueryParams = <T extends Record<string, QueryParamValue>>(
  params: T,
): Partial<Record<keyof T, string | number | boolean>> => {
  const cleanedEntries = Object.entries(params).flatMap(([key, value]) => {
    if (value === undefined || value === null) {
      return [];
    }

    if (typeof value === "string") {
      const trimmed = value.trim();
      if (!trimmed) {
        return [];
      }
      return [[key, trimmed]];
    }

    return [[key, value]];
  });

  return Object.fromEntries(cleanedEntries) as Partial<
    Record<keyof T, string | number | boolean>
  >;
};
