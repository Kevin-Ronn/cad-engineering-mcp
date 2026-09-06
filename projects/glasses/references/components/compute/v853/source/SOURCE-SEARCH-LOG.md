schema_version: 1
v853_pinout_source_search_log:
  id: v853_pinout_source_search_log
  date: 2026-09-05
  target_file: V853/V853S_PINOUT.sls
  target_path_in_repo: projects/glasses/references/components/compute/v853/source/V853_V853S_PINOUT.sls
  status: NOT_OBTAINABLE_FROM_PUBLIC_SOURCES
  reason: "The V853/V853S_PINOUT.sls file is part of the Allwinner NDA datasheet package. The public PDF datasheet (v853-amp-v853s_datasheet_v1.1.pdf, mirrored in projects/glasses/references/components/compute/v853/) states in section 2.2: 'For details about pin description of the V853/V853S, see the V853/V853S_PINOUT.sls.' The .sls file is not redistributed by Allwinner publicly. The V853 Tina Linux SDK (the closest public source) does NOT include the .sls file either. Per the brief, a different V853S/V851S/V853-related SoC pinout is NOT to be substituted unless it is explicitly the same package."

  sources_consulted:
    - name: "ProjectYosemite (YuzukiHD/ProjectYosemite) - Hardware/Datasheets folder"
      url: "https://github.com/YuzukiHD/ProjectYosemite/tree/main/Datasheets"
      result: "PDF datasheet only. The .sls / .xls / .xlsx pinout file is NOT in this repository. Files present: AXP2101_Datasheet_V1_en.pdf, AXP2101设计指南_V1.0_CN.pdf, v853-amp-v853s_datasheet_v1.1 1.pdf, v853-amp-v853s_datasheet_v1.1 2.pdf, v853-brief_en_v1.4.pdf, README."

    - name: "ProjectYosemite (YuzukiHD/ProjectYosemite) - Hardware/Project folder (EasyEDA Pro)"
      url: "https://github.com/YuzukiHD/ProjectYosemite/tree/main/Hardware/Project"
      result: "EasyEDA Pro native project ZIP. Does not contain the V853/V853S_PINOUT.sls file. The EasyEDA Pro format stores per-instance ball-to-component mappings; the underlying ball map is in the Allwinner-supplied .sls."

    - name: "DongshanPI/TinaSDK-Docs (Allwinner Tina SDK documentation)"
      url: "https://github.com/DongshanPI/TinaSDK-Docs"
      result: "9009 files in the tree, NONE of them is V853/V853S_PINOUT.sls. The Tina SDK documentation is HTML/Markdown, not a per-SoC pinout Excel."

    - name: "DongshanPI/100ASK_V853-PRO_TinaSDK (the actual V853 BSP)"
      url: "https://github.com/DongshanPI/100ASK_V853-PRO_TinaSDK"
      result: "15659 files in the tree. Found the actual V853 device tree files: device/config/chips/v853/configs/100ask/board.dts, device/config/chips/v853/configs/100ask/uboot-board.dts, device/config/chips/v853/configs/100ask/sys_config.fex. These are the de-facto pin maps used by Allwinner's BSP. They include the per-pin mux settings and are the BEST public alternative to the .sls file, but they are not the same file format and not the same data (the .sls is the per-ball pad map; the device tree is the per-function mux map). No V853/V853S_PINOUT.sls file."

    - name: "linux-sunxi/sunxi-tools"
      url: "https://github.com/linux-sunxi/sunxi-tools"
      result: "Source code of the FEL utility and other Allwinner tools. No V853 pinout or datasheet file. This repository does NOT contain the .sls file."

    - name: "Scribd (third-party)"
      url: "https://www.scribd.com/document/518932030/V853-Datasheet-V1-0"
      result: "A third-party upload of the V853 Datasheet V1.0 (PDF, 86 pages, Sep 2021). This is the same PDF as the YuzukiHD mirror (a slightly older version, V1.0 instead of V1.1). The .sls file is NOT in this upload."

    - name: "Allwinner official site"
      url: "https://www.allwinnertech.com/"
      result: "Allwinner does not publicly distribute the V853/V853S_PINOUT.sls file. The full datasheet package (PDF + .sls) is available only through Allwinner FAE / direct contact, typically behind an NDA."

    - name: "CSDN / 100ask / whycan / oshwhcb (Chinese-language community sites)"
      url: "various; not searched in this pass due to WebFetch 403 errors"
      result: "Likely contain BSP / FEX / device-tree snippets. The .sls file is a deliverable from the Allwinner NDA datasheet package, not a community resource."

  best_public_alternative:
    file: "device/config/chips/v853/configs/100ask/board.dts + uboot-board.dts + sys_config.fex"
    source: "DongshanPI/100ASK_V853-PRO_TinaSDK"
    url: "https://github.com/DongshanPI/100ASK_V853-PRO_TinaSDK/tree/master/device/config/chips/v853"
    description: "The V853 device tree and sys_config.fex ARE the public authoritative pin map. They contain the per-pin function mux settings and are what the Linux kernel and U-Boot use. They are NOT the V853/V853S_PINOUT.sls file. The .sls file is the per-ball pad map (which ball is which pin number), while the device tree is the per-function mux map (which function is on which pin). For PCB routing, both are needed. The .sls file provides the per-ball physical location; the device tree provides the per-function mapping. The relationship is: physical ball -> pin number -> mux function (per .sls); mux function -> driver (per device tree). Without the .sls file, the per-ball physical location is NOT publicly available."
    note: "The board.dts is the SPECIFIC 100ASK V853-Pro board configuration. The V853 SoC pinctrl dtsi (which would be the SoC-level mux table) is in device/config/chips/v853/, but the per-ball physical pad map is in the .sls file. The device tree and the .sls file are complementary, not substitutes."

  recommendation:
    primary_action: "Acquire the V853/V853S_PINOUT.sls file from Allwinner directly (NDA datasheet package). The V853 datasheet V1.1 PDF (Rev 1.1, 2022-03-23) is the cover sheet; the .sls is the companion file in the same NDA package."
    contact: "Allwinner Technology (allwinnertech.com). The typical path is to contact Allwinner FAE / sales with an NDA request. Distributors (LCSC, Mouser, DigiKey) may also provide the NDA package for active customers."
    fallback_action: "If the .sls cannot be obtained in a reasonable time, use the V853 device tree (board.dts + uboot-board.dts + sys_config.fex from DongshanPI/100ASK_V853-PRO_TinaSDK) as a working approximation for the per-function mux map, AND use the official V853 pinctrl driver in the Linux kernel (drivers/pinctrl/sunxi/pinctrl-v853.c or similar) for the per-ball register map. This is not a substitute for the .sls but provides enough information to design a PCB that connects to the V853's standard interfaces."
    target_location_in_repo: "projects/glasses/references/components/compute/v853/source/V853_V853S_PINOUT.sls"
    target_file_NOT_yet_created: true

  per_brief_compliance:
    brief_rule: "Do NOT substitute a different V853S/V851S/V853-related SoC pinout unless it is explicitly confirmed to be the same package."
    compliance: "PASS. No substitution was made. The .sls file is NOT publicly obtainable. The search is recorded here as required by the brief (source URL, package/version, date, SHA256). The SHA256 field is N/A because no file was obtained."

  files_created_in_this_pass:
    - projects/glasses/references/components/compute/v853/source/SOURCE-SEARCH-LOG.md (this file)
  no_file_created_at_target_path: true
  target_path_directory_created: "projects/glasses/references/components/compute/v853/source/"
  reason_no_target_file: "The V853/V853S_PINOUT.sls file is part of the Allwinner NDA datasheet package. It is not publicly redistributable. Per the brief, no substitute may be used. The correct next step is to acquire the file from Allwinner (NDA) and place it at the target path. This acquisition is a separate action requiring user authorization and an NDA."

  stop_point: "Per the brief: 'STOP after obtaining and documenting the pinout source.' The pinout source has been documented; the pinout file itself could not be obtained. Awaiting user direction on whether to proceed with the public device-tree fallback or to halt pending NDA acquisition."
