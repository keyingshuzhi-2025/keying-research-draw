module.exports = {
  root: true,
  env: {
    browser: true,
    es2022: true,
    node: true
  },
  extends: ["eslint:recommended", "plugin:vue/essential"],
  parserOptions: {
    ecmaVersion: "latest",
    sourceType: "module"
  },
  rules: {
    "no-console": "off",
    "no-unused-vars": "off",
    "no-useless-escape": "off",
    "no-extra-boolean-cast": "off",
    "no-constant-condition": "off",
    "vue/multi-word-component-names": "off"
  }
};
