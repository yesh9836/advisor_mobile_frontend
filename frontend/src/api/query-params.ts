export type QueryParamValue = string | number | boolean | null | undefined;

type QueryParamInput<T extends object> = {
  [K in keyof T]: T[K] extends QueryParamValue ? T[K] : never;
};

export const normalizeQueryParams = <T extends object>(
  params: QueryParamInput<T>,
): Partial<Record<keyof T, string | number | boolean>> => {
  const cleanedEntries = Object.entries(
    params as Record<string, QueryParamValue>,
  ).flatMap(([key, value]) => {
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
