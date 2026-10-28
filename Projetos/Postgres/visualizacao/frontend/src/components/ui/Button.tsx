import { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost" | "accent";
type Size = "sm" | "md";

const VARIANT: Record<Variant, string> = {
  primary: "btn-primary",
  secondary: "btn-secondary",
  ghost: "btn-ghost",
  accent: "btn-accent",
};

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
};

export default function Button({ variant = "primary", size = "md", className = "", ...props }: Props) {
  return (
    <button
      type="button"
      className={`${VARIANT[variant]} ${size === "sm" ? "btn-sm" : ""} ${className}`.trim()}
      {...props}
    />
  );
}
