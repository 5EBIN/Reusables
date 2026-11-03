# ui-primitives

**Category:** ui-kit  
**Origin:** extracted from a production Next.js/FastAPI app.

## What it does
Accessible primitives: Button, Card, Dialog with focus trap and key handling, Sheet, Menu, Tabs, SegmentedControl, Table, TagInput, Toast, Field, Switch, Notice, Timeline, KeyValue, CodeBlock.

## Problem it solved
One place for the look and keyboard behaviour of controls.

## Public interface
* `components/ui/Button.tsx`: `type ButtonVariant`
* `components/ui/Button.tsx`: `type ButtonSize`
* `components/ui/Button.tsx`: `interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>`
* `components/ui/Button.tsx`: `const Button`
* `components/ui/Button.tsx`: `interface IconButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'aria-label'>`
* `components/ui/Button.tsx`: `const IconButton`
* `components/ui/Card.tsx`: `function Card(`
* `components/ui/Card.tsx`: `function GroupedList(`
* `components/ui/Card.tsx`: `function GroupedRow(`
* `components/ui/CodeBlock.tsx`: `function CodeBlock(`
* `components/ui/ConfirmDialog.tsx`: `function ConfirmDialog(`
* `components/ui/Dialog.tsx`: `function Dialog(`
* `components/ui/Empty.tsx`: `function Empty(`
* `components/ui/Empty.tsx`: `function Skeleton(`
* `components/ui/Field.tsx`: `function Field(`
* `components/ui/Field.tsx`: `function Input(`
* `components/ui/Field.tsx`: `function Select(`
* `components/ui/Field.tsx`: `function Textarea(`
* `components/ui/KeyValue.tsx`: `function KeyValue(`
* `components/ui/Menu.tsx`: `interface MenuItem`
* `components/ui/Menu.tsx`: `function Menu(`
* `components/ui/Notice.tsx`: `type NoticeTone`
* `components/ui/Notice.tsx`: `function Notice(`
* `components/ui/SegmentedControl.tsx`: `interface Segment<T extends string>`
* `components/ui/SegmentedControl.tsx`: `function SegmentedControl<T extends string>(`
* `components/ui/Sheet.tsx`: `function Sheet(props: Omit<ComponentProps<typeof Dialog>, 'placement'>)`
* `components/ui/Switch.tsx`: `function Switch(`
* `components/ui/Table.tsx`: `interface Column<Row>`
* `components/ui/Table.tsx`: `function Table<Row>(`
* `components/ui/Tabs.tsx`: `interface TabItem<T extends string>`
* `components/ui/Tabs.tsx`: `function Tabs<T extends string>(`
* `components/ui/Tag.tsx`: `function Tag(`
* `components/ui/Tag.tsx`: `function Count(`
* `components/ui/TagInput.tsx`: `function TagInput(`
* `components/ui/Timeline.tsx`: `interface TimelineItem`
* `components/ui/Timeline.tsx`: `function Timeline(`
* `components/ui/toast.ts`: `const notify`
* `lib/cx.ts`: `const cx`
* `lib/cx.ts`: `const FOCUS`
* `lib/dialogKeys.ts`: `type DismissAction`
* ... and 3 more

## Dependencies
JavaScript (`deps.json`): `lucide-react`, `react`, `react-hot-toast`

## Stubs and what the host must provide
No stubs: every import resolves inside the module.

## Known limits
Needs the token module; icons use lucide-react.

## Quality
B (helper functions covered by the token/theme tests; components untested)  
Tests copied: 0 (copied from the source, not run here).

## How to reuse
Import from `components/ui`.
