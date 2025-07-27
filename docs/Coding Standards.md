<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# AIPerf Coding Standards Guidelines

#### Imports
- Anything in common should be preferred to be imported from the base most level after the common, so `aiperf.common.enums` vs `aiperf.common.enums.message_enums`.
- Always use fully qualified import names within your own parent module, so `aiperf.common.enums.message_enums.py` should import base enums from `aiperf.common.enums.base_enums` and not `aiperf.common.enums`

#### Import Restrictions in `aiperf/common`
- `constants.py` - NO imports allowed at all
- `enums` - NO imports other than `base_enums.py`

- `types.py` - `enums` only. Everything else in `TYPE_CHECKING`
- `exceptions.py` - `types`, (`enums`?)
- `decorators.py` - `types`
- `hooks.py` - `enums`, `types`
- `factories.py` - `enums`, `exceptions`, `types`

- `models` - `enums`, `types`, `constants`
- `messages` - `enums`, `models`, `constants` (`config` ?)
- `protocols.py` - `enums`, `models`, `constants`, `types`, `hooks`. Everything else in `TYPE_CHECKING`
- `config` - `enums`, `constants`, `types`, `models`
- `mixins`

#### Enums
- Prefer to use enums whenever possible as opposed to hard-coded strings.
- Use `CaseInsensitiveStrEnum` as base for all string based enums
- Compare enums to strings directly with `==`, do not use `.value` or `str()`
- Prefer string enums over the use of `auto()`.
  - This allows for re-ordering, adding more, etc.
  - Better serialization
- When defining an enum for a type that is potentially user expandable, create a type `MyEnumT = MyEnum | str`
  - This will keep the

#### Messages


#### Types


#### Pydantic


#### Config


#### Tests