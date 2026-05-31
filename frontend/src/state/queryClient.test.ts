import { describe, expect, it } from "vitest";
import { createAppQueryClient, queryClientDefaults } from "./queryClient";

describe("createAppQueryClient", () => {
  it("uses the shared frontend server-state defaults", () => {
    const client = createAppQueryClient();
    const options = client.getDefaultOptions();

    expect(options.queries?.refetchOnWindowFocus).toBe(false);
    expect(options.queries?.staleTime).toBe(queryClientDefaults.staleTime);
    expect(options.queries?.gcTime).toBe(queryClientDefaults.gcTime);
    expect(options.queries?.structuralSharing).toBe(true);
    expect(options.queries?.retry).toBe(false);
    expect(options.mutations?.retry).toBe(false);
  });
});
