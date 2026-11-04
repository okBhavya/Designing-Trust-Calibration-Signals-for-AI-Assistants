export function readableText(element: HTMLElement): string {
  return (element.innerText || element.textContent || '').trim();
}

export function textNodes(element: HTMLElement): Text[] {
  const walker = element.ownerDocument.createTreeWalker(element, NodeFilter.SHOW_TEXT);
  const nodes: Text[] = [];
  let node: Node | null = walker.nextNode();
  while (node) {
    if (node.textContent?.trim()) nodes.push(node as Text);
    node = walker.nextNode();
  }
  return nodes;
}

export function nearestPreviousText(
  container: HTMLElement,
  root: ParentNode,
  selectors: string[],
): string {
  const elements = Array.from(root.querySelectorAll<HTMLElement>(selectors.join(',')));
  const previous = elements
    .filter((element) => Boolean(element.compareDocumentPosition(container) & Node.DOCUMENT_POSITION_FOLLOWING))
    .at(-1);
  return previous ? readableText(previous) : '';
}
