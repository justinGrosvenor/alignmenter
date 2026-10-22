import assert from "node:assert/strict";
export function verifyBraces(braces) {
	const nested = (depth, open = "{", close = "}") => `${open.repeat(depth)}a,b${close.repeat(depth)}`;
	for (const method of ["parse", "compile", "expand", "stringify"]) {
		for (const options of [{}, { maxDepth: Infinity }, { maxDepth: 10000 }, { maxDepth: NaN }]) {
			assert.throws(() => braces[method](nested(4998), options), /exceeds max depth/);
			assert.throws(() => braces[method](nested(101, "(", ")"), options), /exceeds max depth/);
		}
		assert.doesNotThrow(() => braces[method](nested(100)));
		assert.throws(() => braces[method]("{{a,b},c}", { maxDepth: 1 }), /exceeds max depth/);
		assert.doesNotThrow(() => braces[method]("{{a,b},c}", { maxDepth: 2 }));
	}
	// Public AST overloads must not bypass the parser's bound.
	for (const method of ["compile", "expand", "stringify"]) {
		let ast = { type: "text", value: "a" };
		for (let n = 0; n < 101; n++) ast = { type: "brace", nodes: [ast] };
		assert.throws(() => braces[method]({ type: "root", nodes: [ast] }), /exceeds max depth/);
	}
	assert.deepEqual(braces.expand("src/{a,b}/{1..3}.ts"), [
		"src/a/1.ts",
		"src/a/2.ts",
		"src/a/3.ts",
		"src/b/1.ts",
		"src/b/2.ts",
		"src/b/3.ts",
	]);
	assert.equal(braces.compile("src/{a,b}.ts"), "src/(a|b).ts");
	assert.equal(braces.stringify(braces.parse("a/{b,c}/d")), "a/{b,c}/d");
	assert.deepEqual(braces.expand("\\{literal\\}"), ["{literal}"]);
	assert.deepEqual(braces.expand("{a..c}"), ["a", "b", "c"]);
}

