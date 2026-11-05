// A small stand-in for DOM elements, with classes, attributes, styles and events,
// for the battle pane and split. fake-dom.js only builds nodes from text.
export class Element {
  constructor(tag = "div") {
    this.tag = tag;
    this.children = [];
    this.parent = null;
    this.attributes = {};
    this.listeners = {};
    this.styleProps = {};
    this.classes = new Set();
    this.textContent = "";
    this.hidden = false;
    this.value = "";
    this.scrolled = 0;
    this.style = {
      setProperty: (name, value) => {
        this.styleProps[name] = value;
      },
      removeProperty: (name) => {
        delete this.styleProps[name];
      },
    };
    const element = this;
    this.classList = {
      toggle(name, force) {
        const on = force === undefined ? !element.classes.has(name) : force;
        if (on) element.classes.add(name);
        else element.classes.delete(name);
        return on;
      },
      add: (...names) => names.forEach((n) => this.classes.add(n)),
      remove: (...names) => names.forEach((n) => this.classes.delete(n)),
      contains: (name) => this.classes.has(name),
    };
  }

  get className() {
    return [...this.classes].join(" ");
  }

  set className(value) {
    this.classes = new Set(value.split(/\s+/).filter(Boolean));
  }

  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }

  getAttribute(name) {
    return this.attributes[name] ?? null;
  }

  appendChild(child) {
    child.parent = this;
    this.children.push(child);
    return child;
  }

  append(...nodes) {
    for (const node of nodes) {
      if (typeof node === "string") {
        const text = new Element("#text");
        text.textContent = node;
        this.appendChild(text);
      } else {
        this.appendChild(node);
      }
    }
  }

  replaceChildren(...nodes) {
    this.children = [];
    this.append(...nodes);
  }

  addEventListener(type, handler) {
    (this.listeners[type] ??= []).push(handler);
  }

  dispatch(type, event = {}) {
    const full = { type, target: this, ...event };
    full.preventDefault = () => {
      full.defaultPrevented = true;
    };
    let node = full.target;
    while (node) {
      for (const handler of node.listeners[type] ?? []) handler({ ...full, currentTarget: node });
      node = node.parent;
    }
    return full;
  }

  closest(selector) {
    for (let node = this; node; node = node.parent) {
      if (node.matches(selector)) return node;
    }
    return null;
  }

  matches(selector) {
    if (selector.startsWith(".")) return this.classes.has(selector.slice(1));
    return this.tag === selector;
  }

  setPointerCapture() {}

  scrollIntoView(options) {
    this.scrolled += 1;
    this.scrollOptions = options;
  }

  getBoundingClientRect() {
    return this.rect ?? { left: 0, top: 0, right: 1000, bottom: 600, width: 1000, height: 600 };
  }

  all(predicate) {
    const found = [];
    for (const child of this.children) {
      if (predicate(child)) found.push(child);
      found.push(...child.all(predicate));
    }
    return found;
  }

  byClass(name) {
    return this.all((node) => node.classes.has(name));
  }

  byTag(tag) {
    return this.all((node) => node.tag === tag);
  }

  allText() {
    return [this.textContent, ...this.children.map((child) => child.allText())].join(" ").replace(/\s+/g, " ").trim();
  }
}

export function installDom() {
  globalThis.document = { createElement: (tag) => new Element(tag) };
}

export function fakeStorage(initial = {}) {
  const data = { ...initial };
  return {
    data,
    getItem: (key) => data[key] ?? null,
    setItem: (key, value) => {
      data[key] = String(value);
    },
  };
}
