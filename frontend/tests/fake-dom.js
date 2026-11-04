// A minimal stand-in for the DOM: enough for code that builds nodes from text.
class FakeNode {
  constructor(tag) {
    this.tag = tag;
    this.children = [];
    this.listeners = {};
    this.textContent = "";
    this.disabled = false;
    this.hidden = false;
  }

  appendChild(child) {
    this.children.push(child);
    return child;
  }

  replaceChildren(...nodes) {
    this.children = [...nodes];
    this.textContent = "";
  }

  addEventListener(type, handler) {
    this.listeners[type] = handler;
  }

  click() {
    if (!this.disabled) this.listeners.click?.();
  }

  find(tag) {
    const found = [];
    for (const child of this.children) {
      if (child.tag === tag) found.push(child);
      found.push(...child.find(tag));
    }
    return found;
  }
}

export function installFakeDom() {
  globalThis.document = { createElement: (tag) => new FakeNode(tag) };
  return new FakeNode("root");
}
