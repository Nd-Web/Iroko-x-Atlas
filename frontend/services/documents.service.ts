import axios from "axios";
import type {
  DocumentAnalyticsResponse,
  DocumentListResponse,
  DocumentResponse,
  DocumentSearchRequest,
  DocumentSearchResponse,
} from "@/lib/types";

const api = axios.create({ headers: { "Content-Type": "application/json" } });

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const message =
      err.response?.data?.error ?? "Something went wrong. Please try again.";
    return Promise.reject(new Error(message));
  }
);

export type DocumentListParams = {
  department?: string;
  doc_type?: string;
  status?: string;
  page?: number;
  page_size?: number;
};

export const documentsService = {
  listDocuments: (params: DocumentListParams = {}): Promise<DocumentListResponse> => {
    const p = new URLSearchParams();
    if (params.department) p.set("department", params.department);
    if (params.doc_type) p.set("doc_type", params.doc_type);
    if (params.status) p.set("status", params.status);
    if (params.page) p.set("page", String(params.page));
    if (params.page_size) p.set("page_size", String(params.page_size));
    return api
      .get<DocumentListResponse>(`/api/documents?${p.toString()}`)
      .then((r) => r.data);
  },

  getDocument: (documentId: string): Promise<DocumentResponse> =>
    api.get<DocumentResponse>(`/api/documents/${documentId}`).then((r) => r.data),

  uploadDocument: (formData: FormData): Promise<DocumentResponse> =>
    axios
      .post<DocumentResponse>("/api/documents", formData)
      .then((r) => r.data),

  deleteDocument: (documentId: string): Promise<void> =>
    api.delete(`/api/documents/${documentId}`).then(() => undefined),

  getAnalytics: (days?: number): Promise<DocumentAnalyticsResponse> => {
    const p = new URLSearchParams();
    if (days !== undefined) p.set("days", String(days));
    const qs = p.toString();
    return api
      .get<DocumentAnalyticsResponse>(`/api/documents/analytics${qs ? `?${qs}` : ""}`)
      .then((r) => r.data);
  },

  searchDocuments: (params: DocumentSearchRequest): Promise<DocumentSearchResponse> => {
    const p = new URLSearchParams({ q: params.q });
    if (params.top !== undefined) p.set("top", String(params.top));
    if (params.doc_type) p.set("doc_type", params.doc_type);
    if (params.classification) p.set("classification", params.classification);
    if (params.source) p.set("source", params.source);
    if (params.rerank !== undefined) p.set("rerank", String(params.rerank));
    return api
      .get<DocumentSearchResponse>(`/api/documents/search?${p.toString()}`)
      .then((r) => r.data);
  },
};
