import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import {
  OPERATOR_TOKEN_SESSION_KEY,
  persistOperatorToken,
  removeOperatorToken,
  restoreOperatorToken,
} from "./operator-session.ts";

class TestStorage implements Storage {
  private readonly values = new Map<string, string>();

  get length() { return this.values.size; }
  clear() { this.values.clear(); }
  getItem(key: string) { return this.values.get(key) ?? null; }
  key(index: number) { return [...this.values.keys()][index] ?? null; }
  removeItem(key: string) { this.values.delete(key); }
  setItem(key: string, value: string) { this.values.set(key, value); }
}

test("restores a persisted operator token", () => {
  const storage = new TestStorage();
  storage.setItem(OPERATOR_TOKEN_SESSION_KEY, "  restored-token  ");
  assert.equal(restoreOperatorToken(storage), "restored-token");
});

test("persists an activated operator token", () => {
  const storage = new TestStorage();
  persistOperatorToken("activated-token", storage);
  assert.equal(storage.getItem(OPERATOR_TOKEN_SESSION_KEY), "activated-token");
});

test("removes a deactivated operator token", () => {
  const storage = new TestStorage();
  storage.setItem(OPERATOR_TOKEN_SESSION_KEY, "activated-token");
  removeOperatorToken(storage);
  assert.equal(storage.getItem(OPERATOR_TOKEN_SESSION_KEY), null);
});

test("operator session implementation never uses localStorage", () => {
  const source = fs.readFileSync(path.join(process.cwd(), "src", "lib", "operator-session.ts"), "utf8");
  assert.doesNotMatch(source, /localStorage/);
  assert.match(source, /window\.sessionStorage/);
});
