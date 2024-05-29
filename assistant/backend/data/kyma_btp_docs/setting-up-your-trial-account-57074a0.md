

<link rel="stylesheet" type="text/css" href="../css/sap-icons.css"/>

# Setting Up Your Trial Account

Your global trial account is set up automatically, so that you can start using it right away. However, if one or more of the automatic steps fail, you can also finalize the setup manually by following the steps below.





## Create Your Trial Subaccount

The first thing that is needed in the setup of your trial account is the creation of a subaccount. If this step was successful in the SAP BTP cockpit, you can directly skip to the next section.





## Procedure

1.  Navigate into your global account by choosing *Enter Your Trial Account*.

2.  Choose *New Subaccount*.

3.  Configure your trial account:


    <table>
    <tr>
    <th valign="top">

    Field
    
    </th>
    <th valign="top">

    Input
    
    </th>
    </tr>
    <tr>
    <td valign="top">
    
    Display Name

    > ### Note:  
    > The value for this parameter is a sample one, you can provide a name of your choice.


    
    </td>
    <td valign="top">
    
    `trial`
    
    </td>
    </tr>
    <tr>
    <td valign="top">
    
    **Description**
    
    </td>
    <td valign="top">
    
    Optional
    
    </td>
    </tr>
    <tr>
    <td valign="top">
    
    **Provider**
    
    </td>
    <td valign="top">
    
    Desired infrastructure provider
    
    </td>
    </tr>
    <tr>
    <td valign="top">
    
    **Region**
    
    </td>
    <td valign="top">
    
    Desired region
    
    </td>
    </tr>
    <tr>
    <td valign="top">
    
    **Subdomain**
    
    </td>
    <td valign="top">
    
    `<your_id>trial`

    Example: **P0123456789trial**
    
    </td>
    </tr>
    <tr>
    <td valign="top">
    
    **Enable beta features**
    
    </td>
    <td valign="top">
    
    Optional

    Enables the use of beta services and applications.
    
    </td>
    </tr>
    <tr>
    <td valign="top">
    
    **Custom Properties**
    
    </td>
    <td valign="top">
    
    Optional

    You can use custom properties to identify and organize the subaccounts in your global account. For example, you can filter subaccounts by custom property in some cockpit pages.
    
    </td>
    </tr>
    </table>
    





## Results

You have successfully set up your trial subaccount.





## Add Entitlements

Once you have a subaccount \(whether it was created automatically or you followed the steps described above\), you need entitlements to get your trial up and running.





## Procedure

1.  Navigate to your subaccount by choosing its tile.

2.  Choose *Entitlements* from the left-hand side navigation.

3.  Choose *Configure Entitlements* to enter edit mode.

4.  Choose *Add Service Plans* and select all the service plans available for your subaccount.

    > ### Note:  
    > To select a service plan, choose a service from the left and tick all the service plans that appear on the right. Do that for all services.

5.  Once you've added all the service plans, you see them all in a table. Before you choose Save, for all the plans with numerical quota, choose :heavy_plus_sign: to increase the amount to the maximum \(until the icon becomes disabled\).

6.  Finally, choose *Save* to save all your changes and exit edit mode.






## Enable Trial Kyma Environment

After you’ve successfully added the entitlements, you can enable your trial Kyma environment and start developing.



## Procedure

1.  Navigate to your subaccount.

2.  Create your Kyma environment. For details, see [Create the Kyma Instance](create-the-kyma-instance-09dd313.md).

3.  Provide the name of your cluster and, optionally, a description.

    Wait until the cluster is provisioned and you see the link to the Kyma dashboard.

4.  Access the Kyma dashboard. For further information on the development options, see [Development in the Kyma Environment](development-in-the-kyma-environment-606ec61.md).






## Results

Your trial Kyma environment is ready to use.





## Disable Expired Trial Kyma Environment

After your trial Kyma environment has expired, you must disable it to remove all the data connected to the cluster from SAP systems.



## Procedure

1.  Navigate to your subaccount.

2.  In the *Kyma Environment* section of your subaccount overview, click *Disable Kyma*.

    > ### Note:  
    > On deletion of the expired cluster, we attempt to delete the Service Instances that you created with the cluster. If we cannot do that, you have to [remove the Service Instances yourself](https://help.sap.com/docs/SERVICEMANAGEMENT/09cc82baadc542a688176dce601398de/99016f83ce8e4d049316b61b5cadf1fc.html) before you disable such a *Kyma Environment*.






## Extend Trial Kyma Environment

You cannot extend your trial Kyma environment. After your trial Kyma environment has expired, you must disable it on your subaccount and enable it again to create a new cluster.



## Procedure

1.  Navigate to your subaccount.

2.  [Disable your expired Kyma environment.](setting-up-your-trial-account-57074a0.md#loiod022bb1dde7d499685ee6ef3ab825680)

3.  After your Kyma environment has been successfully disabled, [create a new Kyma environment.](setting-up-your-trial-account-57074a0.md#loio6313afa84b8940f7963ceec0bb236780) 


