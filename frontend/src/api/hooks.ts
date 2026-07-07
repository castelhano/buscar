import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";

export function useList<T>(chave: string, caminho: string, params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: [chave, params],
    queryFn: () => api.get<T[]>(caminho, params),
  });
}

export function useItem<T>(chave: string, caminho: string, habilitado = true) {
  return useQuery({
    queryKey: [chave],
    queryFn: () => api.get<T>(caminho),
    enabled: habilitado,
  });
}

export function useCreate<T, C = Partial<T>>(chave: string, caminho: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: C) => api.post<T>(caminho, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [chave] }),
  });
}

export function useUpdate<T, C = Partial<T>>(chave: string, caminhoBase: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: C }) => api.put<T>(`${caminhoBase}/${id}`, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [chave] }),
  });
}

export function useRemove(chave: string, caminhoBase: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.delete(`${caminhoBase}/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [chave] }),
  });
}
