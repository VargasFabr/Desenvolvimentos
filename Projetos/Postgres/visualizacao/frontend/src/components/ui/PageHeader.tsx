import { ReactNode } from "react";

type Props = {
  title: string;
  actions?: ReactNode;
};

export default function PageHeader({ title, actions }: Props) {
  return (
    <header className="page-header">
      <h2 className="page-title">{title}</h2>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </header>
  );
}
