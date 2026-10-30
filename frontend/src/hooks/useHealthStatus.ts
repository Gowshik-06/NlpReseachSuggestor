import { useEffect, useState } from "react";
import { getHealth } from "../services/api";
import type { HealthStatus } from "../types/health";

export type LoadState = "loading" | "success" | "error";

interface UseHealthStatusResult {
  state: LoadState;
  data: HealthStatus | null;
  errorMessage: string | null;
}

export function useHealthStatus(): UseHealthStatusResult {
  const [state, setState] = useState<LoadState>("loading");
  const [data, setData] = useState<HealthStatus | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    getHealth()
      .then((result) => {
        if (!isMounted) return;
        setData(result);
        setState("success");
      })
      .catch((err: Error) => {
        if (!isMounted) return;
        setErrorMessage(err.message);
        setState("error");
      });

    return () => {
      isMounted = false;
    };
  }, []);

  return { state, data, errorMessage };
}
