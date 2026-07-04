import { type FC, memo } from "react";
import ReactMarkdown from "react-markdown";
import rehypeRaw from "rehype-raw";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";
import type { MarkdownRendererProps } from "@/types/renderer";

const MarkdownRenderer: FC<MarkdownRendererProps> = ({
  content,
  className,
}) => {
  return (
    <div
      className={cn(
        "prose dark:prose-invert text-sm max-w-none text-slate-200",
        className,
      )}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw]}
        components={{
          ul: ({ children }) => <ul className="list-disc pl-5 my-2 space-y-1 text-slate-300">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal pl-5 my-2 space-y-1 text-slate-300">{children}</ol>,
          li: ({ children }) => <li className="text-slate-300 leading-relaxed pl-0.5">{children}</li>,
          p: ({ children }) => <p className="mb-2 leading-relaxed text-slate-200 last:mb-0">{children}</p>,
          strong: ({ children }) => <strong className="font-bold text-slate-100">{children}</strong>,
          em: ({ children }) => <em className="italic text-slate-300">{children}</em>,
          h1: ({ children }) => <h1 className="text-lg font-bold text-slate-100 my-2">{children}</h1>,
          h2: ({ children }) => <h2 className="text-base font-bold text-slate-100 my-2">{children}</h2>,
          h3: ({ children }) => <h3 className="text-sm font-bold text-slate-100 my-1">{children}</h3>,
          table: ({ children }) => (
            <div className="overflow-x-auto my-3 rounded-lg border border-slate-800 bg-slate-950/40">
              <table className="min-w-full divide-y divide-slate-800 text-xs text-slate-300">
                {children}
              </table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-slate-900/60 text-slate-200 font-semibold">{children}</thead>,
          tbody: ({ children }) => <tbody className="divide-y divide-slate-800 bg-slate-950/20">{children}</tbody>,
          tr: ({ children }) => <tr className="hover:bg-slate-800/30 transition-colors">{children}</tr>,
          th: ({ children }) => <th className="px-3 py-2 text-left border-b border-slate-800">{children}</th>,
          td: ({ children }) => <td className="px-3 py-2 border-b border-slate-800/50">{children}</td>,
          code({ className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || "");
            const isInline = !match && !String(children).includes("\n");
            return !isInline ? (
              <pre className="bg-slate-950/90 p-3 rounded-lg overflow-x-auto border border-slate-800 my-2 text-xs font-mono text-cyan-400">
                <code>{children}</code>
              </pre>
            ) : (
              <code className="bg-slate-800/80 px-1.5 py-0.5 rounded text-cyan-300 font-mono text-xs" {...props}>
                {children}
              </code>
            );
          },
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sky-400 hover:text-sky-300 underline transition-colors"
            >
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};

export default memo(MarkdownRenderer);
