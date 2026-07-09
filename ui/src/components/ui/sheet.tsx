import * as React from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Drawer latéral (« Sheet ») bâti sur le `Dialog` Radix : un panneau pleine hauteur
 * qui glisse depuis la **droite**. Même API que `dialog.tsx` (Root/Trigger/Close/…),
 * donc on convertit une modale en remplaçant `Dialog*` par `Sheet*`.
 *
 * Agencement : `SheetContent` est une **colonne flex pleine hauteur**. On y place
 * `SheetHeader` (fixe), `SheetBody` (corps **scrollable** — `flex-1 overflow-y-auto`)
 * et `SheetFooter` (fixe). Un composant flottant interne (ex. `DatePicker`) doit donc
 * se portaliser (cf. `DatePicker`) pour ne pas allonger le scroll du `SheetBody`.
 */
export const Sheet = DialogPrimitive.Root;
export const SheetTrigger = DialogPrimitive.Trigger;
export const SheetClose = DialogPrimitive.Close;

export const SheetContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>
>(({ className, children, ...props }, ref) => (
  <DialogPrimitive.Portal>
    <DialogPrimitive.Overlay
      className={cn(
        "fixed inset-0 z-50 bg-black/40",
        "data-[state=open]:[animation:overlay-in_0.2s_ease] data-[state=closed]:[animation:overlay-out_0.15s_ease]",
      )}
    />
    <DialogPrimitive.Content
      ref={ref}
      className={cn(
        "fixed inset-y-0 right-0 z-50 flex h-full w-full max-w-md flex-col border-l border-line bg-white shadow-xl outline-none",
        "data-[state=open]:[animation:sheet-in-right_0.28s_cubic-bezier(0.32,0.72,0,1)]",
        "data-[state=closed]:[animation:sheet-out-right_0.2s_ease-in]",
        className,
      )}
      {...props}
    >
      {children}
      <DialogPrimitive.Close className="absolute right-4 top-4 rounded-sm text-muted hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-navy/40">
        <X className="size-4" />
        <span className="sr-only">Fermer</span>
      </DialogPrimitive.Close>
    </DialogPrimitive.Content>
  </DialogPrimitive.Portal>
));
SheetContent.displayName = "SheetContent";

/** En-tête fixe (ne défile pas). */
export function SheetHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex shrink-0 flex-col gap-1.5 border-b border-line px-6 py-4 pr-12", className)} {...props} />;
}

/** Corps **scrollable** : c'est lui qui défile quand le contenu dépasse la hauteur. */
export function SheetBody({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("min-h-0 flex-1 overflow-y-auto px-6 py-4", className)} {...props} />;
}

/** Pied fixe (ne défile pas). */
export function SheetFooter({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("flex shrink-0 flex-wrap justify-end gap-2 border-t border-line px-6 py-4", className)}
      {...props}
    />
  );
}

export const SheetTitle = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title ref={ref} className={cn("text-lg font-semibold text-ink", className)} {...props} />
));
SheetTitle.displayName = "SheetTitle";

export const SheetDescription = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Description>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Description>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Description ref={ref} className={cn("text-sm text-muted", className)} {...props} />
));
SheetDescription.displayName = "SheetDescription";
