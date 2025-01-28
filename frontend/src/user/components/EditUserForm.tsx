import { type ReadonlySignal, useComputed, useSignal } from "@preact/signals";

import { groupNames } from "@dashlive/options";
import { EditUserState, UseAllUsersHook, UserValidationErrors } from "../../hooks/useAllUsers";
import { StaticInputProps } from "../../types/StaticInputProps";
import { SetValueFunc } from "../../types/SetValueFunc";
import { InputFieldRow } from "../../components/InputFieldRow";
import { useMemo } from "preact/hooks";

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
  setValue: SetValueFunc;
  validateUser: UseAllUsersHook["validateUser"];
  newUser?: boolean;
}

export function EditUserForm({
  user,
  setValue,
  validateUser,
  newUser = false,
}: EditUserFormProps) {
  const disabledFields = useSignal<Record<string, boolean>>({});
  const formFields: StaticInputProps[] = useMemo(() => {
    return fields.map((field) => {
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
  }, [newUser]);
  const errors = useComputed<UserValidationErrors>(() => validateUser(user.value));

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
