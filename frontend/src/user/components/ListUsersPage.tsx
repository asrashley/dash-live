import { ReadonlySignal } from "@preact/signals-core";
import { Link } from "wouter-preact";
import { useCallback, useContext } from "preact/hooks";

import { uiRouteMap } from "@dashlive/routemap";
import {
  createSortableTable,
  RenderCellProps,
} from "../../components/SortableTable";
import {
  EditUserState,
  FlattenedUserState,
  useAllUsers,
} from "../../hooks/useAllUsers";
import { BooleanCell } from "../../components/BooleanCell";
import { AppStateContext } from "../../appState";
import { EndpointContext } from "../../endpoints";
import { AddUserDialog } from "./AddUserDialog";

const headings: [keyof FlattenedUserState, string][] = [
  ["pk", "#"],
  ["username", "Username"],
  ["email", "Email"],
  ["lastLogin", "Last Login"],
  ["mustChange", "Must Change"],
  ["adminGroup", "Admin"],
  ["mediaGroup", "Media"],
  ["userGroup", "User"],
];

function renderCell({ field, row }: RenderCellProps<FlattenedUserState>) {
  const { username } = row;
  switch (field) {
    case "username":
      return (
        <Link href={uiRouteMap.editUser.url({ username })}>{username}</Link>
      );
    case "email":
      return (
        <Link href={uiRouteMap.editUser.url({ username })}>{row.email}</Link>
      );
    case "lastLogin":
      return <span>{row.lastLogin ?? "---"}</span>;
    case "mustChange":
    case "adminGroup":
    case "mediaGroup":
    case "userGroup":
      return <BooleanCell value={row[field]} />;
    default:
      return <span>{row[field]}</span>;
  }
}

const UsersTable = createSortableTable<FlattenedUserState>({
  headings,
  primaryKey: "pk",
  initialSortField: "username",
  renderCell,
});

interface ListUsersTableProps {
  users: ReadonlySignal<FlattenedUserState[]>;
}

function ListUsersTable({ users }: ListUsersTableProps) {
  return <UsersTable data={users} caption="Users" />;
}

export default function ListUsersPage() {
  const { dialog } = useContext(AppStateContext);
  const apiRequests = useContext(EndpointContext);
  const { flattenedUsers, validateUser, addUser } = useAllUsers();
  const openAddUserDialog = useCallback(() => {
    dialog.value = {
      backdrop: true,
      addUser: {
        active: true,
      },
    };
  }, [dialog]);
  const closeDialog = useCallback(() => {
    dialog.value = null;
  }, [dialog]);
  const saveNewUser = useCallback(
    async (user: EditUserState) => {
      const errs = validateUser(user);
      if (errs.username) {
        return errs.username;
      }
      if (errs.password) {
        return errs.password;
      }
      try {
        const result = await apiRequests.addUser(user);
        if (result.success) {
          addUser(result.user);
          return "";
        }
        return result.errors.join("\n");
      } catch (err) {
        return `failed to add new user - ${err}`;
      }
    },
    [addUser, apiRequests, validateUser]
  );

  return (
    <div id="user-management" className="container">
      <div className="d-flex flex-row">
        <h1 className="flex-grow-1">User Accounts</h1>
        <button
          onClick={openAddUserDialog}
          className="btn btn-success add-user"
        >
          Add New User
        </button>
      </div>
      <div className="users-list-wrap">
        <ListUsersTable users={flattenedUsers} />
      </div>
      <AddUserDialog
        onClose={closeDialog}
        saveChanges={saveNewUser}
        validateUser={validateUser}
      />
    </div>
  );
}
