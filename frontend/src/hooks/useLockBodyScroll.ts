import { useEffect } from "react";

/** Trava o scroll do body enquanto o componente que chama isso estiver montado (ex: um modal aberto). */
export function useLockBodyScroll() {
  useEffect(() => {
    const overflowOriginal = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = overflowOriginal;
    };
  }, []);
}
