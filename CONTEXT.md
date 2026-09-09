# pybalmorel

Python tooling for pre- and post-processing around the Balmorel energy system model, including the `weatheryear` module that converts external model outputs (CorRES, demand, hydro, COP) into Balmorel-ready `.inc` files for a chosen historical weather year.

## Language

### Weather-year preprocessing

**CapDev timestep**:
A representative `Season.Hour` pair (e.g. `S02.T073`) used for the reduced capacity-development (investment) time resolution. Built as the cross product of `CapDev_timesteps_to_keep.S` (representative seasons) and `.T` (representative hours) — both are lists of equal standing, not a season-plus-hours pair.
_Avoid_: CapDev season (a single `S` value is not itself a timestep)

**Day-Ahead (DA) resolution**:
The full hourly time series for a weather year, before it is reduced to CapDev timesteps.
_Avoid_: full resolution, raw resolution

**tech_to_keep**:
The list of technology-run folder names (e.g. `Future_Onshore`, `PV_Rooftop`) that `WEATHERYEAR.get_vre_data()` actually processes when exporting VRE time series from CorRES. Folders present under `weatheryear_inputs_folder` but not listed here are silently skipped; a folder that matches no recognized technology category at all raises instead of being skipped.

**turbine_to_keep**:
A finer filter within the `Future_Onshore`/`Future_Offshore_*` `tech_to_keep` categories, naming which specific turbine models (e.g. `SP277-HH100`) are processed. PV categories have no equivalent finer level — each PV `tech_to_keep` category is already a single model, varying only by resource grade.
_Avoid_: PV_to_keep (removed — PV data has no per-model dimension to filter)

**Technology identity**:
The `(turbine/PV model, resource grade, onshore/offshore, region)` tuple that uniquely identifies one renewable generation technology instance. `GGG_renewable`, `INVDATASET_renewable`, and `AAA_renewable` each spell this differently for their own set domain, but all derive from this one shared identity so their spellings can't independently drift.

**GGG_renewable**:
Balmorel generator (`GGG`) identifiers for renewable technologies, one per technology identity per investment vintage year (e.g. `GNR_WT-SP335-HH100_ONS_RG1_Y-2020`).

**INVDATASET_renewable**:
Renewable investment-option identifiers Balmorel's investment mode chooses among, one per technology identity, independent of region or vintage year (e.g. `VRE-ONS_SP335-HH100_RG1`).

**AAA_renewable**:
Region-qualified technology identifiers, one per technology identity per region, used to say where that technology is available (e.g. `IE_VRE-ONS_SP335-HH100_RG1`).

**INVDATA**:
The GAMS parameter linking an `AAA_renewable` member to the `INVDATASET_renewable` member it can invest in.
