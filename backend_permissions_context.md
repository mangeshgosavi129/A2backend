# Backend Permissions & Role Context

This document outlines the current Role-Based Access Control (RBAC) implementation in the backend to guide frontend development for the "Team Management" features.

## 1. Role Hierarchy
The system uses the following roles (Enum), ordered by privilege level (highest to lowest):

1.  **`owner`**: Full access. Identify as the creator of the Organisation.
    *   *Unique Capability*: Can assign roles to other users.
2.  **`manager`**: Operational admin.
    *   Can manage tasks (create, assign, delete), clients, and users.
    *   *Cannot* assign roles to others.
3.  **`employee`**: Standard user.
    *   Can create tasks.
    *   Can update tasks they are assigned to.
    *   *Cannot* assign tasks to others or see all organisation tasks (unless assigned).
4.  **`intern`**: Restricted user.
    *   *Cannot* create tasks.
    *   Can only view and update tasks specifically assigned to them.

## 2. Permissions Matrix

| Feature | Owner | Manager | Employee | Intern |
| :--- | :---: | :---: | :---: | :---: |
| **User Mgmt** | | | | |
| Assign Roles | ✅ | ❌ | ❌ | ❌ |
| Delete/Modify Users | ✅ | ✅ | ❌ | ❌ |
| **Task Mgmt** | | | | |
| Create Task | ✅ | ✅ | ✅ | ❌ |
| Assign Task | ✅ | ✅ | ❌ | ❌ |
| Cancel/Delete Task | ✅ | ✅ | ❌ | ❌ |
| Update Any Task | ✅ | ✅ | ❌ | ❌ |
| Update *Own* Task | ✅ | ✅ | ✅ | ✅ |
| View All Tasks | ✅ | ✅ | ❌ | ❌ |
| **Other** | | | | |
| Manage Clients | ✅ | ✅ | ❌ | ❌ |
| Manage Checklists | ✅ | ✅ | ✅ (Own) | ✅ (Own) |

## 3. API Reference for Role Management

To allow an **Owner** to change permissions for their team, use the following endpoints:

### A. List Team Members & Roles
**Endpoint**: `GET /organisations/{org_id}/roles`
**Header**: `Authorization: Bearer <token>`
**Response**:
```json
[
  {
    "user_id": 12,
    "user_name": "Alice Smith",
    "role": "manager",
    "assigned_at": "2024-12-01T10:00:00"
  },
  {
    "user_id": 15,
    "user_name": "Bob Jones",
    "role": "employee",
    "assigned_at": "2024-12-02T11:30:00"
  }
]
```

### B. Assign/Change Role
**Endpoint**: `POST /organisations/{org_id}/roles`
**Permissions**: Only accessible by users with `role="owner"`.
**Payload**:
```json
{
  "user_id": 15,
  "role": "manager"  // Options: "manager", "employee", "intern"
}
```
**Response (200 OK)**:
```json
{
  "message": "Role updated to manager for user 15"
}
```

## 4. Frontend Implementation Guide (Suggestions)

1.  **"Team" Settings Page**:
    *   Create a view accessible to users where `currentUser.role === 'owner' || currentUser.role === 'manager'`.
    *   **Note**: Managers can view/delete users, but *cannot* change roles.
    *   Display a table of all users in the organisation using `GET /organisations/{org_id}/roles`.
2.  **Role Editor**:
    *   In the table row for each user, provide a Dropdown menu for the "Role" column.
    *   Options: `Manager`, `Employee`, `Intern`.
    *   On change, trigger `POST /organisations/{org_id}/roles`.
3.  **Visual Feedback**:
    *   Show a toast notification on success ("Role updated").
    *   Handle errors (e.g., if a non-owner tries to change it, backend returns 403).

## 5. Other Relevant API Constraints
*   **Clients**: Only Managers/Owners can create/edit clients. Hide "Add Client" button for Employees/Interns.
*   **Task Assignment**: Hide the "Assign To" dropdown/modal for Employees/Interns. They cannot assign tasks.
