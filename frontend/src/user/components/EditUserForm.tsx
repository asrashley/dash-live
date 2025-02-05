import { type ReadonlySignal } from "@preact/signals";
import { useMemo } from "preact/hooks";

import { groupNames } from "@dashlive/options";
import { UserValidationErrors } from "../../hooks/useAllUsers";
import { EditUserState } from "../../types/EditUserState";
import { StaticInputProps } from "../../types/StaticInputProps";
import { SetValueFunc } from "../../types/SetValueFunc";
import { InputFieldRow } from "../../components/InputFieldRow";

type CgiFormInputItem = Omit<
  StaticInputProps,
  "fullName" | "shortName" | "prefix"
>;

const fields: CgiFormInputItem[] = [
  {
    name: "username",
    title: "Username",
    type: "text",
  },
  {
    name: "email",
    title: "Email",
    type: "email",
  },
  {
    name: "password",
    title: "Password",
    type: "password",
    placeholder: "***",
  },
  {
    name: "confirmPassword",
    title: "Confirm Password",
    type: "password",
    placeholder: "***",
  },
  {
    name: "mustChange",
    text: "User must change password at next login?",
    title: "Must Change",
    type: "checkbox",
  },
  {
    name: "groups",
    type: "multiselect",
    title: "Groups",
    options: groupNames.map((name: string) => ({
      name: `${name.toLowerCase()}Group`,
      title: name,
      value: name,
    })),
  },
];

export interface EditUserFormProps {
  user: ReadonlySignal<EditUserState>;
  errors: ReadonlySignal<UserValidationErrors>;
  disabledFields: ReadonlySignal<Record<string, boolean>>;
  only?: string[];
  setValue: SetValueFunc;
  newUser?: boolean;
}

export function EditUserForm({
  user,
  setValue,
  errors,
  disabledFields,
  only,
  newUser = false,
}: EditUserFormProps) {
  const formFields: StaticInputProps[] = useMemo(() => {
    const result = fields.map((field) => {
      const rv: StaticInputProps = {
        ...field,
        shortName: field.name,
        fullName: field.name,
        prefix: "",
      };
      if (newUser && field.type === "password") {
        rv.allowReveal = true;
      }
      return rv;
    });
    if (only) {
      return result.filter(({name}) => only.includes(name));
    }
    return result;
  }, [newUser, only]);

  return (
    <form>
      {formFields.map((field) => (
        <InputFieldRow
          mode="cgi"
          data={user}
          disabledFields={disabledFields}
          errors={errors}
          key={field.fullName}
          setValue={setValue}
          {...field}
        />
      ))}
    </form>
  );
}
