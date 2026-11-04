/** Tiny helper to build DOM nodes. Text is always set as text (never HTML). */
export function h(tag, props = {}, ...children) {
    const node = document.createElement(tag)
    for (const [key, value] of Object.entries(props)) {
        if (value === false || value === null || value === undefined) continue;
        if (key === "class") node.className = value;
        else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
        else if (value === true) node.setAttribute(key, "");
        else node.setAttribute(key, value);
    }
    for (const child of children.flat()) {
        if (child === null || child === undefined || child === false) continue;
        node.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return node;
}