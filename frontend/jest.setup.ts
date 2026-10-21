import "@testing-library/jest-dom";

// jsdom does not implement scrollIntoView; provide a no-op so components that
// scroll evidence into view do not throw in tests.
if (typeof Element !== "undefined" && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}
