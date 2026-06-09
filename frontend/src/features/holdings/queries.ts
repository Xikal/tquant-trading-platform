import { useMutation, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "../../app/query/queryKeys";

export function useSaveHoldingMutation(save: () => Promise<unknown>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: save,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: queryKeys.holdings });
      void client.invalidateQueries({ queryKey: queryKeys.monitor });
    },
  });
}
