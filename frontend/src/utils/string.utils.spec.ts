import { normalize } from "./string.utils";

describe("String utils", () => {
  it("should remove Romanian diacritics", () => {
    expect(normalize("București")).toBe("bucuresti");
  });

  it("should convert text to lowercase", () => {
    expect(normalize("LONDON")).toBe("london");
  });

  it("should remove all Romanian diacritics", () => {
    expect(normalize("ȚĂȘÎÂ")).toBe("tasia");
  });

  it("should leave normal text unchanged except lowercase", () => {
    expect(normalize("Cluj")).toBe("cluj");
  });

  it("should return an empty string", () => {
    expect(normalize("")).toBe("");
  });
});
