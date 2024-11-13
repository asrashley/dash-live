import { fieldGroups, defaultOptions } from "/libs/options.js";

const byFieldName = {};
const byFullName = {};
const byShortName = {};
const prefixes = [];

fieldGroups.forEach((grp) => {
  let src = defaultOptions;
  let fullNameDest = byFullName;
  if (grp.name !== "general") {
    prefixes.push(grp.name);
    byFullName[grp.name] = {};
    fullNameDest = byFullName[grp.name];
    src = defaultOptions[grp.name];
  }
  grp.fields.forEach((field) => {
    byFieldName[field.name] = field;
    if (field.value !== undefined) {
      field.defaultValue = field.value;
    }
    if (!field.fullName) {
      if (field.prefix) {
        field.fullName = field.name.slice(field.prefix.length + 2);
      } else {
        field.fullName = field.name;
      }
    }
    fullNameDest[field.fullName] = field;
    field.defaultValue = src[field.fullName];
    if (!field.shortName) {
      field.shortName = field.name;
    }
    byShortName[field.shortName] = field;
  });
});

function notEqual(defaultValue, value) {
  if (defaultValue === undefined || defaultValue === null) {
    return !!value;
  }
  if (Array.isArray(defaultValue)) {
    if (defaultValue.length === 0 && !value) {
      return false;
    }
    if (Array.isArray(value)) {
      if (defaultValue.length !== value.length) {
        return true;
      }
      return value.some((val, idx) => defaultValue[idx] !== val);
    }
  }
  return defaultValue !== value;
}

export function nonDefaultOptions(options) {
  const result = Object.fromEntries(prefixes.map((key) => [key, {}]));
  for (const [key, value] of Object.entries(options)) {
    if (prefixes.includes(key)) {
      for (const [pk, pval] of Object.entries(value)) {
        const field = byFullName[key][pk];
        if (notEqual(field?.defaultValue, pval)) {
          result[key][pk] = pval;
        }
      }
    } else {
      const field = byFullName[key];
      if (notEqual(field.defaultValue, value)) {
        result[key] = value;
      }
    }
  }
  return result;
}

export function optionsToShortNames(options) {
  const fields = [];
  for (const [key, value] of Object.entries(options)) {
    if (prefixes.includes(key)) {
      for (const [pk, pval] of Object.entries(value)) {
        const { shortName } = byFullName[key][pk];
        fields.push([shortName, pval]);
      }
    } else {
      const { shortName } = byFullName[key];
      fields.push([shortName, value]);
    }
  }
  return Object.fromEntries(fields);
}

export function shortNamesToOptions(data) {
  if (!data) {
    return undefined;
  }
  const result = Object.fromEntries(prefixes.map((key) => [key, {}]));
  for (const [key, value] of Object.entries(data)) {
    const field = byShortName[key];
    if (!field) {
      console.warn(`Failed to find "${key}"`);
      continue;
    }
    if (field.prefix) {
      result[field.prefix][field.fullName] = value;
    } else {
      result[field.fullName] = value;
    }
  }
  return result;
}

export function formToOptions(form) {
  const result = Object.fromEntries(prefixes.map((key) => [key, {}]));
  const data = new FormData(form);
  for (let i = 0; i < form.elements.length; ++i) {
    const elt = form.elements.item(i);
    if (elt.nodeName === "BUTTON") {
        continue;
    }
    const key = elt.name;
    if (!key) {
        continue;
    }
    let value = data[key] ?? elt.type === "checkbox" ? elt.checked : elt.value;
    const { fullName, prefix, type, defaultValue } = byFieldName[key] ?? {};
    if (fullName === undefined) {
      continue;
    }
    if (type === "checkbox") {
      value = /(true)|(on)/.test(value);
    } else if (type === "number") {
      value = parseInt(value, 10);
      if (isNaN(value)) {
        value = defaultValue ?? null;
      }
    }
    if (prefix) {
      result[prefix][fullName] = value;
    } else {
      result[fullName] = value;
    }
  }
  return result;
}

export function optionsToFormData(options) {
  if (options === undefined) {
    return undefined;
  }
  const opts = {
    ...JSON.parse(JSON.stringify(defaultOptions)),
    ...options,
  };
  const data = {};
  for (const [key, value] of Object.entries(opts)) {
    if (prefixes.includes(key)) {
      for (let [pk, pval] of Object.entries(value)) {
        const { name } = byFullName[key][pk];
        data[`${key}__${name}`] = pval;
      }
    } else {
      const field = byFullName[key];
      if (field) {
        data[field.name] = value;
      }
    }
  }
  return data;
}
