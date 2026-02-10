export interface ApiValidationIssue {
  loc: Array<string | number>;
  msg: string;
  type: string;
}

export interface ApiError {
  detail: string | ApiValidationIssue[];
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}
