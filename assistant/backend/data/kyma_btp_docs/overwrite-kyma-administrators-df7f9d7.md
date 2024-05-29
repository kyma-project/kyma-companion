

# Overwrite Kyma Administrators

In some cases, you may need to overwrite usernames of the current administrators, for example, if they forget their password or leave the organization and nobody can access your Kyma runtime.





## Prerequisites

-   You’re the subaccount administrator.






## Context

To overwrite the names for the `cluster-admin` role, update the Kyma instance and provide a new value for the *administrators* field.

> ### Caution:  
> This procedure overwrites current administrators and shouldn't be used to add new ones. Treat it as an emergency self-service procedure in case of lost access. To provide access to new users, the `cluster-admin` should create a RoleBinding and/or a ClusterRoleBinding in the runtime. See [RoleBinidng and ClusterRoleBinding](https://kubernetes.io/docs/reference/access-authn-authz/rbac/#rolebinding-and-clusterrolebinding) in the official Kubernetes documentation.





## Procedure

1.  In the SAP BTP cockpit, go to your Kyma instance and select *Update*.

2.  Provide a new set of administrators' usernames as an array of strings.

    > ### Remember:  
    > Use administrators' email addresses as their usernames.

    In a JSON file, use the following structure:

    ```
    "administrators": [
            "example_1@mail.com",
            "example_2@mail.com",
            "example_3@mail.com"
        ]
    ```

3.  Click *Update*.






## Results

Your Kyma instance is updated with the new administrators' usernames.

**Related Information**  


[Provisioning and Updating Parameters in the Kyma Environment](provisioning-and-updating-parameters-in-the-kyma-environment-e2e13bf.md "You can configure the cluster parameters in the Kyma environment.")

