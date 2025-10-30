from Scripts.datasets import os_data
from Scripts.datasets import chipset_data
from Scripts import acpi_guru
from Scripts import compatibility_checker
from Scripts import config_prodigy
from Scripts import gathering_files
from Scripts import hardware_customizer
from Scripts import kext_maestro
from Scripts import run
from Scripts import smbios
from Scripts import utils
import updater
import os
import sys
import re
import shutil
import traceback
import time

class OCPE:
    def __init__(self):
        self.u = utils.Utils("OpCore Simplify")
        self.u.clean_temporary_dir()
        self.ac = acpi_guru.ACPIGuru()
        self.c = compatibility_checker.CompatibilityChecker()
        self.co = config_prodigy.ConfigProdigy()
        self.o = gathering_files.gatheringFiles()
        self.h = hardware_customizer.HardwareCustomizer()
        self.k = kext_maestro.KextMaestro()
        self.s = smbios.SMBIOS()
        self.r = run.Run()
        self.result_dir = self.u.get_temporary_dir()

    def select_hardware_report(self):
        self.ac.dsdt = self.ac.acpi.acpi_tables = None

        while True:
            self.u.head("Select hardware report")
            print("")
            if os.name == "nt":
                print("\033[1;93mNote:\033[0m")
                print("- Ensure you are using the latest version of Hardware Sniffer before generating the hardware report.")
                print("- Hardware Sniffer will not collect information related to Resizable BAR option of GPU (disabled by default) and monitor connections in Windows PE.")
                print("")
                print("E. Export hardware report (Recommended)")
                print("")
            print("Q. Quit")
            print("")
        
            user_input = self.u.request_input("Drag and drop your hardware report here (.JSON) or type \"E\" to export: ")
            if user_input.lower() == "q":
                self.u.exit_program()
            if user_input.lower() == "e":
                hardware_sniffer = self.o.gather_hardware_sniffer()

                output = self.r.run({
                    "args":[hardware_sniffer, "-e"]
                })
                
                if output[-1] != 0:
                    print("")
                    print("Could not export the hardware report. Please export it manually using Hardware Sniffer.")
                    print("")
                    self.u.request_input()
                    return
                else:
                    report_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "SysReport", "Report.json")
                    acpitables_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "SysReport", "ACPI")

                    report_data = self.u.read_file(report_path)
                    self.ac.read_acpi_tables(acpitables_dir)
                    
                    return report_path, report_data
                
            path = self.u.normalize_path(user_input)
            data = self.u.read_file(path)
            
            if not path or os.path.splitext(path)[1].lower() != ".json" or not isinstance(data, dict):
                print("")
                print("Invalid file. Please ensure it is a valid \"Report.json\" file.")
                print("")
                self.u.request_input()
                continue
            
            return path, data
        
    def show_oclp_warning(self):
        while True:
            self.u.head("OpenCore Legacy Patcher Warning")
            print("")
            print("1. OpenCore Legacy Patcher is the only solution to enable dropped GPU and Broadcom WiFi")
            print("   support in newer macOS versions, as well as to bring back AppleHDA for macOS Tahoe 26.")
            print("")
            print("2. OpenCore Legacy Patcher disables macOS security features including SIP and AMFI, which may")
            print("   lead to issues such as requiring full installers for updates, application crashes, and")
            print("   system instability.")
            print("")
            print("3. OpenCore Legacy Patcher is not officially supported for Hackintosh community.")
            print("")
            print("\033[91mImportant:\033[0m")
            print("Please consider these risks carefully before proceeding.")
            print("")
            print("\033[1;93mNote:\033[0m")
            print("If you experience black screen after login with OpenCore Legacy Patcher v2.2.0 or newer")
            print("after applying root patches, please revert to version v2.1.2.")
            print("")
            option = self.u.request_input("Do you want to continue with OpenCore Legacy Patcher? (yes/No): ").strip().lower()
            if option == "yes":
                return True
            elif option == "no":
                return False

    def select_macos_version(self, hardware_report, native_macos_version, ocl_patched_macos_version):
        suggested_macos_version = native_macos_version[1]
        version_pattern = re.compile(r'^(\d+)(?:\.(\d+)(?:\.(\d+))?)?$')

        for device_type in ("GPU", "Network", "Bluetooth", "SD Controller"):
            if device_type in hardware_report:
                for device_name, device_props in hardware_report[device_type].items():
                    if device_props.get("Compatibility", (None, None)) != (None, None):
                        if device_type == "GPU" and device_props.get("Device Type") == "Integrated GPU":
                            device_id = device_props.get("Device ID", ""*8)[5:]

                            if device_props.get("Manufacturer") == "AMD" or device_id.startswith(("59", "87C0")):
                                suggested_macos_version = "22.99.99"
                            elif device_id.startswith(("09", "19")):
                                suggested_macos_version = "21.99.99"

                        if self.u.parse_darwin_version(suggested_macos_version) > self.u.parse_darwin_version(device_props.get("Compatibility")[0]):
                            suggested_macos_version = device_props.get("Compatibility")[0]

        while True:
            if "Beta" in os_data.get_macos_name_by_darwin(suggested_macos_version):
                suggested_macos_version = "{}{}".format(int(suggested_macos_version[:2]) - 1, suggested_macos_version[2:])
            else:
                break

        while True:
            self.u.head("Select macOS Version")
            if native_macos_version[1][:2] != suggested_macos_version[:2]:
                print("")
                print("\033[1;36mSuggested macOS version:\033[0m")
                print("- For better compatibility and stability, we suggest you to use only {} or older.".format(os_data.get_macos_name_by_darwin(suggested_macos_version)))
            print("")
            print("Available macOS versions:")
            print("")

            oclp_min = int(ocl_patched_macos_version[-1][:2]) if ocl_patched_macos_version else 99
            oclp_max = int(ocl_patched_macos_version[0][:2]) if ocl_patched_macos_version else 0
            min_version = min(int(native_macos_version[0][:2]), oclp_min)
            max_version = max(int(native_macos_version[-1][:2]), oclp_max)

            for darwin_version in range(min_version, max_version + 1):
                name = os_data.get_macos_name_by_darwin(str(darwin_version))
                label = " (\033[1;93mRequires OpenCore Legacy Patcher\033[0m)" if oclp_min <= darwin_version <= oclp_max else ""
                print("   {}. {}{}".format(darwin_version, name, label))

            print("")
            print("\033[1;93mNote:\033[0m")
            print("- To select a major version, enter the number (e.g., 19).")
            print("- To specify a full version, use the Darwin version format (e.g., 22.4.6).")
            print("")
            print("Q. Quit")
            print("")
            option = self.u.request_input("Please enter the macOS version you want to use (default: {}): ".format(os_data.get_macos_name_by_darwin(suggested_macos_version))) or suggested_macos_version
            if option.lower() == "q":
                self.u.exit_program()

            match = version_pattern.match(option)
            if match:
                target_version = "{}.{}.{}".format(match.group(1), match.group(2) if match.group(2) else 99, match.group(3) if match.group(3) else 99)
                
                if ocl_patched_macos_version and self.u.parse_darwin_version(ocl_patched_macos_version[-1]) <= self.u.parse_darwin_version(target_version) <= self.u.parse_darwin_version(ocl_patched_macos_version[0]):
                    return target_version
                elif self.u.parse_darwin_version(native_macos_version[0]) <= self.u.parse_darwin_version(target_version) <= self.u.parse_darwin_version(native_macos_version[-1]):
                    return target_version

    def build_opencore_efi(self, hardware_report, disabled_devices, smbios_model, macos_version, needs_oclp):
        steps = [
            "Copying EFI base to results folder",
            "Applying ACPI patches",
            "Copying kexts and snapshotting to config.plist",
            "Generating config.plist",
            "Cleaning up unused drivers, resources, and tools"
        ]
        
        title = "Building OpenCore EFI"

        self.u.progress_bar(title, steps, 0)
        self.u.create_folder(self.result_dir, remove_content=True)

        if not os.path.exists(self.k.ock_files_dir):
            raise Exception("Directory '{}' does not exist.".format(self.k.ock_files_dir))
        
        source_efi_dir = os.path.join(self.k.ock_files_dir, "OpenCorePkg")
        shutil.copytree(source_efi_dir, self.result_dir, dirs_exist_ok=True)

        config_file = os.path.join(self.result_dir, "EFI", "OC", "config.plist")
        config_data = self.u.read_file(config_file)
        
        if not config_data:
            raise Exception("Error: The file {} does not exist.".format(config_file))
        
        self.u.progress_bar(title, steps, 1)
        config_data["ACPI"]["Add"] = []
        config_data["ACPI"]["Delete"] = []
        config_data["ACPI"]["Patch"] = []
        if self.ac.ensure_dsdt():
            self.ac.hardware_report = hardware_report
            self.ac.disabled_devices = disabled_devices
            self.ac.acpi_directory = os.path.join(self.result_dir, "EFI", "OC", "ACPI")
            self.ac.smbios_model = smbios_model
            self.ac.lpc_bus_device = self.ac.get_lpc_name()

            for patch in self.ac.patches:
                if patch.checked:
                    if patch.name == "BATP":
                        patch.checked = getattr(self.ac, patch.function_name)()
                        self.k.kexts[kext_maestro.kext_data.kext_index_by_name.get("ECEnabler")].checked = patch.checked
                        continue

                    acpi_load = getattr(self.ac, patch.function_name)()

                    if not isinstance(acpi_load, dict):
                        continue

                    config_data["ACPI"]["Add"].extend(acpi_load.get("Add", []))
                    config_data["ACPI"]["Delete"].extend(acpi_load.get("Delete", []))
                    config_data["ACPI"]["Patch"].extend(acpi_load.get("Patch", []))
        
        config_data["ACPI"]["Patch"].extend(self.ac.dsdt_patches)
        config_data["ACPI"]["Patch"] = self.ac.apply_acpi_patches(config_data["ACPI"]["Patch"])

        self.u.progress_bar(title, steps, 2)
        kexts_directory = os.path.join(self.result_dir, "EFI", "OC", "Kexts")
        self.k.install_kexts_to_efi(macos_version, kexts_directory)
        config_data["Kernel"]["Add"] = self.k.load_kexts(hardware_report, macos_version, kexts_directory)

        self.u.progress_bar(title, steps, 3)
        self.co.genarate(hardware_report, disabled_devices, smbios_model, macos_version, needs_oclp, self.k.kexts, config_data)
        self.u.write_file(config_file, config_data)

        self.u.progress_bar(title, steps, 4)
        files_to_remove = []

        drivers_directory = os.path.join(self.result_dir, "EFI", "OC", "Drivers")
        driver_list = self.u.find_matching_paths(drivers_directory, extension_filter=".efi")
        driver_loaded = [kext.get("Path") for kext in config_data.get("UEFI").get("Drivers")]
        for driver_path, type in driver_list:
            if not driver_path in driver_loaded:
                files_to_remove.append(os.path.join(drivers_directory, driver_path))

        resources_audio_dir = os.path.join(self.result_dir, "EFI", "OC", "Resources", "Audio")
        if os.path.exists(resources_audio_dir):
            files_to_remove.append(resources_audio_dir)

        picker_variant = config_data.get("Misc", {}).get("Boot", {}).get("PickerVariant")
        if picker_variant in (None, "Auto"):
            picker_variant = "Acidanthera/GoldenGate" 
        if os.name == "nt":
            picker_variant = picker_variant.replace("/", "\\")

        resources_image_dir = os.path.join(self.result_dir, "EFI", "OC", "Resources", "Image")
        available_picker_variants = self.u.find_matching_paths(resources_image_dir, type_filter="dir")

        for variant_name, variant_type in available_picker_variants:
            variant_path = os.path.join(resources_image_dir, variant_name)
            if ".icns" in ", ".join(os.listdir(variant_path)):
                if picker_variant not in variant_name:
                    files_to_remove.append(variant_path)

        tools_directory = os.path.join(self.result_dir, "EFI", "OC", "Tools")
        tool_list = self.u.find_matching_paths(tools_directory, extension_filter=".efi")
        tool_loaded = [tool.get("Path") for tool in config_data.get("Misc").get("Tools")]
        for tool_path, type in tool_list:
            if not tool_path in tool_loaded:
                files_to_remove.append(os.path.join(tools_directory, tool_path))

        for file_path in files_to_remove:
            try:
                if os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                else:
                    os.remove(file_path)
            except Exception as e:
                print("Failed to remove file: {}".format(e))
        
        self.u.progress_bar(title, steps, len(steps), done=True)
        
        print("OpenCore EFI build complete.")
        time.sleep(2)
        
    def check_bios_requirements(self, org_hardware_report, hardware_report):
        requirements = []
        
        org_firmware_type = org_hardware_report.get("BIOS", {}).get("Firmware Type", "Unknown")
        firmware_type = hardware_report.get("BIOS", {}).get("Firmware Type", "Unknown")
        if org_firmware_type == "Legacy" and firmware_type == "UEFI":
            requirements.append("Enable UEFI mode (disable Legacy/CSM (Compatibility Support Module))")

        secure_boot = hardware_report.get("BIOS", {}).get("Secure Boot", "Unknown")
        if secure_boot != "Disabled":
            requirements.append("Disable Secure Boot")
        
        if hardware_report.get("Motherboard", {}).get("Platform") == "Desktop" and hardware_report.get("Motherboard", {}).get("Chipset") in chipset_data.IntelChipsets[112:]:
            resizable_bar_enabled = any(gpu_props.get("Resizable BAR", "Disabled") == "Enabled" for gpu_props in hardware_report.get("GPU", {}).values())
            if not resizable_bar_enabled:
                requirements.append("Enable Above 4G Decoding")
                requirements.append("Disable Resizable BAR/Smart Access Memory")
                
        return requirements

    def before_using_efi(self, org_hardware_report, hardware_report):
        while True:
            self.u.head("Before Using EFI")
            print("")                 
            print("\033[93mPlease complete the following steps:\033[0m")
            print("")
            
            bios_requirements = self.check_bios_requirements(org_hardware_report, hardware_report)
            if bios_requirements:
                print("* BIOS/UEFI Settings Required:")
                for requirement in bios_requirements:
                    print("    - {}".format(requirement))
                print("")
            
            print("* USB Mapping:")
            print("    - Use USBToolBox tool to map USB ports.")
            print("    - Add created UTBMap.kext into the {} folder.".format("EFI\\OC\\Kexts" if os.name == "nt" else "EFI/OC/Kexts"))
            print("    - Remove UTBDefault.kext in the {} folder.".format("EFI\\OC\\Kexts" if os.name == "nt" else "EFI/OC/Kexts"))
            print("    - Edit config.plist:")
            print("        - Use ProperTree to open your config.plist.")
            print("        - Run OC Snapshot by pressing Command/Ctrl + R.")
            print("        - If you have more than 15 ports on a single controller, enable the XhciPortLimit patch.")
            print("        - Save the file when finished.")
            print("")
            print("Type \"AGREE\" to open the built EFI for you\n")
            response = self.u.request_input("")
            if response.lower() == "agree":
                self.u.open_folder(self.result_dir)
                break
            else:
                print("\033[91mInvalid input. Please try again.\033[0m")

    def main(self):
        hardware_report_path = None
        native_macos_version = None
        disabled_devices = None
        macos_version = None
        ocl_patched_macos_version = None
        needs_oclp = False
        smbios_model = None

        while True:
            self.u.head()
            print("")
            print("  Hardware Report: {}".format(hardware_report_path or 'Not selected'))
            if hardware_report_path:
                print("")
                print("  macOS Version:   {}".format(os_data.get_macos_name_by_darwin(macos_version) if macos_version else 'Not selected') + (' (' + macos_version + ')' if macos_version else '') + ('. \033[1;93mRequires OpenCore Legacy Patcher\033[0m' if needs_oclp else ''))
                print("  SMBIOS:          {}".format(smbios_model or 'Not selected'))
                if disabled_devices:
                    print("  Disabled Devices:")
                    for device, _ in disabled_devices.items():
                        print("    - {}".format(device))
            print("")

            print("1. Select Hardware Report")
            print("2. Select macOS Version")
            print("3. Customize ACPI Patch")
            print("4. Customize Kexts")
            print("5. Customize SMBIOS Model")
            print("6. Build OpenCore EFI")
            print("")
            print("Q. Quit")
            print("")

            option = self.u.request_input("Select an option: ")
            if option.lower() == "q":
                self.u.exit_program()
           
            if option == "1":
                hardware_report_path, hardware_report = self.select_hardware_report()
                hardware_report, native_macos_version, ocl_patched_macos_version = self.c.check_compatibility(hardware_report)
                macos_version = self.select_macos_version(hardware_report, native_macos_version, ocl_patched_macos_version)
                customized_hardware, disabled_devices, needs_oclp = self.h.hardware_customization(hardware_report, macos_version)
                smbios_model = self.s.select_smbios_model(customized_hardware, macos_version)
                if not self.ac.ensure_dsdt():
                    self.ac.select_acpi_tables()
                self.ac.select_acpi_patches(customized_hardware, disabled_devices)
                needs_oclp = self.k.select_required_kexts(customized_hardware, macos_version, needs_oclp, self.ac.patches)
                self.s.smbios_specific_options(customized_hardware, smbios_model, macos_version, self.ac.patches, self.k)

            if not hardware_report_path:
                self.u.head()
                print("\n\n")
                print("\033[1;93mPlease select a hardware report first.\033[0m")
                print("\n\n")
                self.u.request_input("Press Enter to go back...")
                continue

            if option == "2":
                macos_version = self.select_macos_version(hardware_report, native_macos_version, ocl_patched_macos_version)
                customized_hardware, disabled_devices, needs_oclp = self.h.hardware_customization(hardware_report, macos_version)
                smbios_model = self.s.select_smbios_model(customized_hardware, macos_version)
                needs_oclp = self.k.select_required_kexts(customized_hardware, macos_version, needs_oclp, self.ac.patches)
                self.s.smbios_specific_options(customized_hardware, smbios_model, macos_version, self.ac.patches, self.k)
            elif option == "3":
                self.ac.customize_patch_selection()
            elif option == "4":
                self.k.kext_configuration_menu(macos_version)
            elif option == "5":
                smbios_model = self.s.customize_smbios_model(customized_hardware, smbios_model, macos_version)
                self.s.smbios_specific_options(customized_hardware, smbios_model, macos_version, self.ac.patches, self.k)
            elif option == "6":
                if needs_oclp and not self.show_oclp_warning():
                    macos_version = self.select_macos_version(hardware_report, native_macos_version, ocl_patched_macos_version)
                    customized_hardware, disabled_devices, needs_oclp = self.h.hardware_customization(hardware_report, macos_version)
                    smbios_model = self.s.select_smbios_model(customized_hardware, macos_version)
                    needs_oclp = self.k.select_required_kexts(customized_hardware, macos_version, needs_oclp, self.ac.patches)
                    self.s.smbios_specific_options(customized_hardware, smbios_model, macos_version, self.ac.patches, self.k)
                    continue

                if not self.o.gather_bootloader_kexts(self.k.kexts, macos_version):
                    continue
                
                self.build_opencore_efi(customized_hardware, disabled_devices, smbios_model, macos_version, needs_oclp)
                self.before_using_efi(hardware_report, customized_hardware)

                self.u.head("Result")
                print("")
                print("Your OpenCore EFI for {} has been built at:".format(customized_hardware.get("Motherboard").get("Name")))
                print("\t{}".format(self.result_dir))
                print("")
                self.u.request_input("Press Enter to main menu...")

if __name__ == '__main__':
    update_flag = updater.Updater().run_update()
    if update_flag:
        os.execv(sys.executable, ['python3'] + sys.argv)

    o = OCPE()
    while True:
        try:
            o.main()
        except Exception as e:
            o.u.head("An Error Occurred")
            print("")
            print(traceback.format_exc())
            o.u.request_input()