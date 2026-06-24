import type { components } from "./schema";

type S = components["schemas"];

export type Template = S["TemplateOut"];
export type Placeholders = S["PlaceholdersOut"];
export type Field = S["FieldOut"];
export type Category = S["CategoryOut"];
export type MailTemplate = S["MailTemplateOut"];
export type MailTemplateIn = S["MailTemplateIn"];
export type Printers = S["PrintersOut"];
export type PrintConfig = S["PrintConfigOut"];
export type Acte = S["ActeOut"];
export type ActeIn = S["ActeIn"];
export type ActeList = S["ActeListOut"];
