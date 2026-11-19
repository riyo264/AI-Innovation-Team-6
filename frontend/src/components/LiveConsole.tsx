import { useEffect, useRef } from "react";

export function LiveConsole({ lines, title = "Live execution output" }: { lines: string[]; title?: string }) {
  const ref = useRef<HTMLPreElement>(null);
  useEffect(() => {
    ref.current?.scrollTo({ top: ref.current.scrollHeight });
  }, [lines.length]);

  return (
    <section className="panel">
      <h3>{title}</h3>
      <pre ref={ref} className="console">
        {lines.length ? lines.join("\n") : "Waiting for output…"}
      </pre>
    </section>
  );
}
