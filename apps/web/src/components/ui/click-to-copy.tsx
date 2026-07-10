import * as React from 'react';
import { Copy, Check } from 'lucide-react';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

export interface ClickToCopyProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  text: string;
  children?: React.ReactNode;
}

export function ClickToCopy({ text, children, className, ...props }: ClickToCopyProps) {
  const [copied, setCopied] = React.useState(false);

  const handleCopy = async (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      toast.success('Copié !', {
        description: `"${text}" a été copié dans le presse-papiers.`,
        duration: 2000,
      });
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error('Erreur lors de la copie');
    }
  };

  return (
    <button
      type="button"
      onClick={handleCopy}
      className={cn(
        'group/copy inline-flex items-center gap-1.5 rounded px-1 py-0.5 text-inherit transition-all duration-200 hover:bg-muted/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer select-text text-left border-transparent bg-transparent outline-none p-0 m-0 w-full justify-between lg:w-auto lg:justify-start',
        className
      )}
      title="Cliquer pour copier"
      {...props}
    >
      <span className="truncate">{children || text}</span>
      <span className={cn(
        'inline-flex size-4 shrink-0 items-center justify-center text-muted transition-all duration-200',
        copied ? 'opacity-100' : 'opacity-0 group-hover/copy:opacity-100 group-focus-visible/copy:opacity-100'
      )}>
        {copied ? (
          <Check className="size-3.5 text-green animate-in zoom-in-50 duration-200" />
        ) : (
          <Copy className="size-3.5 hover:text-ink transition-colors" />
        )}
      </span>
    </button>
  );
}
