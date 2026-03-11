# APIRule Custom Resource <!-- {docsify-ignore-all} -->

The `apirules.gateway.kyma-project.io` CRD describes the kind and the format of data the APIRule Controller uses to configure resources.

> [!WARNING]
> APIRule CRD v2 is the latest stable version. Version v1beta1 is removed in release 3.4 of the API Gateway module.
> All existing v1beta1 APIRule configurations continue to function as expected via conversion webhook, but you can no longer create new v1beta1 APIRules.
> Required action: Migrate all your APIRule custom resources (CRs) to version v2. For the detailed migration procedure, see [APIRule Migration](./apirule-migration/).

Browse the documentation related to the APIRule CR in version `v2`:
- [Specification of APIRule CR](./04-10-apirule-custom-resource.md)
- [APIRule Access Strategies](./04-15-api-rule-access-strategies.md)
- [Changes in APIRule v2](./04-70-changes-in-apirule-v2.md)

Browse the migration guides:
- [Retrieve v1beta1 spec](./apirule-migration/01-81-retrieve-v1beta1-spec.md)
- [Migrate to v2](./apirule-migration/01-82-migrate-allow-noop-no_auth-v1beta1-to-v2.md)
