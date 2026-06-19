import { Loader2 } from 'lucide-react';
import { cn } from '@/shared/lib/utils';

interface SpinnerProps {
  className?: string;
  size?: 'sm' | 'default' | 'lg';
  variant?: 'inline' | 'full-page';
}

export function Spinner({ className, size = 'default', variant = 'inline' }: SpinnerProps) {
  const sizeClass = { sm: 'h-4 w-4', default: 'h-8 w-8', lg: 'h-12 w-12' }[size];
  const content = <Loader2 className={cn('animate-spin text-blue-600', sizeClass, className)} />;

  if (variant === 'full-page') {
    return <div className="flex items-center justify-center py-20">{content}</div>;
  }
  return content;
}
