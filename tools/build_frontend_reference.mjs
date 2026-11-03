import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import ts from "../frontend/app/node_modules/typescript/lib/typescript.js";

class FrontendSymbolReader {
  constructor(root) {
    this.root = root;
  }

  files(directory) {
    return fs.readdirSync(directory, { withFileTypes: true })
      .sort((left, right) => left.name.localeCompare(right.name))
      .flatMap((entry) => {
        const target = path.join(directory, entry.name);
        return entry.isDirectory() ? this.files(target)
          : /\.tsx?$/.test(entry.name) ? [target] : [];
      });
  }

  read(filename) {
    const text = fs.readFileSync(filename, "utf8");
    const source = ts.createSourceFile(filename, text, ts.ScriptTarget.Latest, true);
    if (source.parseDiagnostics.length) {
      throw new Error(ts.formatDiagnosticsWithColorAndContext(source.parseDiagnostics, {
        getCurrentDirectory: () => this.root,
        getCanonicalFileName: (name) => name,
        getNewLine: () => "\n",
      }));
    }
    const symbols = [];
    const visit = (node, scope) => {
      const declaration = ts.isFunctionDeclaration(node) || ts.isClassDeclaration(node)
        || ts.isInterfaceDeclaration(node) || ts.isTypeAliasDeclaration(node)
        || ts.isEnumDeclaration(node) || ts.isEnumMember(node)
        || ts.isVariableDeclaration(node) || ts.isMethodDeclaration(node)
        || ts.isMethodSignature(node) || ts.isPropertyDeclaration(node)
        || ts.isPropertySignature(node) || ts.isGetAccessorDeclaration(node)
        || ts.isSetAccessorDeclaration(node);
      let nested = scope;
      if (declaration && node.name) {
        const name = node.name.getText(source);
        const callable = ts.isFunctionDeclaration(node) || ts.isMethodDeclaration(node)
          || ts.isMethodSignature(node);
        const signature = callable
          ? `(${node.parameters.map((parameter) => parameter.getText(source)).join(", ")})${node.type ? `: ${node.type.getText(source)}` : ""}`
          : node.type ? `: ${node.type.getText(source)}` : "";
        symbols.push({
          name: [...scope, name].join("."),
          kind: ts.SyntaxKind[node.kind],
          line: source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1,
          signature,
        });
        nested = [...scope, name];
      }
      ts.forEachChild(node, (child) => visit(child, nested));
    };
    visit(source, []);
    return { path: path.relative(this.root, filename), symbols };
  }

  run() {
    return this.files(path.join(this.root, "frontend/app/src"))
      .map((filename) => this.read(filename));
  }
}

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
console.log(JSON.stringify(new FrontendSymbolReader(root).run()));
