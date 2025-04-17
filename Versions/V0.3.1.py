import re

def convert_orion_to_rayfield(orion_code: str) -> str:
    text = orion_code
    config_enabled = False

    # 1. replacing the orion library loadstring with the rayfield library loadstring
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if 'OrionLib' in line and 'loadstring' in line:
            # note: using single quotes around the URL.
            lines[i] = 'local Rayfield = loadstring(game:HttpGet(\'https://sirius.menu/rayfield\'))()'
    text = "\n".join(lines)


    # 2. Converting OrionLib:MakeWindow call to Rayfield:CreateWindow
    def replace_makewindow(match):
        nonlocal config_enabled
        content = match.group(1)
        # Remove CloseCallback function if present (Rayfield has no equivalent)
        cc_idx = content.find('CloseCallback')
        if cc_idx != -1:
            func_idx = content.find('function', cc_idx)
            if func_idx != -1:
                nest = 0
                pos = func_idx
                end_idx = -1
                while pos < len(content):
                    next_func = content.find('function', pos + 1)
                    next_end = content.find('end', pos + 1)
                    if next_end == -1:
                        break
                    if next_func != -1 and next_func < next_end:
                        nest += 1
                        pos = next_func
                        continue
                    if nest == 0:
                        end_idx = next_end
                        break
                    else:
                        nest -= 1
                        pos = next_end
                        continue
                if end_idx != -1:
                    end_idx += len('end')
                    after = content[end_idx:]
                    if after.lstrip().startswith(','):
                        end_idx += after.find(',') + 1
                    content = (content[:cc_idx].rstrip().rstrip(',')).rstrip()
        # Parse Window settings in Orion (always execute this, even if no CloseCallback)
        name_match = re.search(r'Name\s*=\s*(["\'].*?["\'])', content)
        save_match = re.search(r'SaveConfig\s*=\s*(true|false)', content)
        folder_match = re.search(r'ConfigFolder\s*=\s*(["\'].*?["\'])', content)
        intro_match = re.search(r'IntroEnabled\s*=\s*(true|false)', content)
        introtext_match = re.search(r'IntroText\s*=\s*(["\'].*?["\'])', content)
        introicon_match = re.search(r'IntroIcon\s*=\s*(["\'].*?["\'])', content)
        icon_match = re.search(r'Icon\s*=\s*(["\'].*?["\']|\d+)', content)
        name_val = name_match.group(1) if name_match else '"Unnamed UI"'
        save_val = save_match.group(1) if save_match else 'false'
        config_enabled = True if save_val == 'true' else False
        folder_val = folder_match.group(1) if folder_match else None
        intro_enabled = True if intro_match and intro_match.group(1) == 'true' else False
        intro_text_val = introtext_match.group(1) if introtext_match else None
        # Process IntroIcon (extract valid assetID if available)
        intro_icon_val = None
        if introicon_match:
            raw = introicon_match.group(1)
            if raw[0] in ('"', "'"):
                inner = raw[1:-1]
                if inner.startswith("rbxassetid://"):
                    intro_icon_val = inner.split("://")[1]
        # Process Icon: only keep if it's a valid asset id (rbxassetid://... or pure digit)
        icon_val = None
        if icon_match:
            raw = icon_match.group(1)
            if raw[0] in ('"', "'"):
                inner = raw[1:-1]
                if inner.startswith("rbxassetid://"):
                    icon_val = inner.split("://")[1]
                elif inner.isdigit():
                    icon_val = inner
                else:
                    icon_val = None   # Omit if not valid
            else:
                if raw.isdigit():
                    icon_val = raw
                else:
                    icon_val = None
        # Build Rayfield:CreateWindow config table
        fields = [f'Name = {name_val}']
        if icon_val:
            fields.append(f'Icon = {icon_val}')
        if intro_enabled:
            if intro_text_val:
                fields.append(f'LoadingTitle = {intro_text_val}')
            if intro_icon_val:
                fields.append('LoadingSubtitle = ""')
        if save_match:
            enabled_str = 'true' if save_val == 'true' else 'false'
            folder_str = folder_val if folder_val else 'nil'
            fields.append(f'ConfigurationSaving = {{ Enabled = {enabled_str}, FolderName = {folder_str}, FileName = "Config" }}')
        return f'Rayfield:CreateWindow({{{", ".join(fields)}}})'


    text = re.sub(r'\w+:MakeWindow\(\{([\s\S]*?)\}\)', replace_makewindow, text)

    # 3. Convert Window:MakeTab to Window:CreateTab
    def replace_maketab(match):
        prefix = match.group(1)
        content = match.group(2)
        name_match = re.search(r'Name\s*=\s*(["\'].*?["\'])', content)
        icon_match = re.search(r'Icon\s*=\s*(["\'].*?["\']|\d+)', content)
        name_val = name_match.group(1) if name_match else '"Tab"'
        icon_arg = ""
        if icon_match:
            raw = icon_match.group(1)
            if raw[0] in ('"', "'"):
                inner = raw[1:-1]
                if inner.startswith("rbxassetid://"):
                    icon_arg = inner.split("://")[1]
                elif inner.isdigit():
                    icon_arg = inner
                else:
                    icon_arg = f'"{inner}"'
            else:
                icon_arg = raw
        if icon_arg:
            return f'{prefix}:CreateTab({name_val}, {icon_arg})'
        else:
            return f'{prefix}:CreateTab({name_val})'
    text = re.sub(r'(\w+):MakeTab\(\{([\s\S]*?)\}\)', replace_maketab, text)

    # 4. Convert Tab:AddSection to Tab:CreateSection
    def replace_addsection(match):
        prefix = match.group(1)
        content = match.group(2)
        name_match = re.search(r'Name\s*=\s*(["\'].*?["\'])', content)
        name_val = name_match.group(1) if name_match else '"Section"'
        return f'{prefix}:CreateSection({name_val})'
    text = re.sub(r'(\w+):AddSection\(\{([\s\S]*?)\}\)', replace_addsection, text)

    # 5. Convert Tab:AddParagraph(title, content) to Tab:CreateParagraph({...})
    def replace_addparagraph(match):
        prefix = match.group(1)
        title_str = match.group(2)
        content_str = match.group(3)
        return f'{prefix}:CreateParagraph({{ Title = {title_str}, Content = {content_str} }})'

    # Handles single- or multi-line Lua strings: "", '', [[...]]
    text = re.sub(
        r'(\w+):AddParagraph\(\s*(["\'].*?["\']|\[\[.*?\]\])\s*,\s*(["\'].*?["\']|\[\[.*?\]\])\s*\)',
        replace_addparagraph,
        text,
        flags=re.DOTALL
    )


    # 6. Convert Tab:AddButton to Tab:CreateButton
    def replace_addbutton(match):
        prefix = match.group(1)
        content = match.group(2)
        # No key changes needed (Name and Callback are same in Rayfield)
        return f'{prefix}:CreateButton({{{content}}})'
    text = re.sub(r'(\w+):AddButton\(\{([\s\S]*?)\}\)', replace_addbutton, text)

    # 7. Convert Tab:AddToggle to Tab:CreateToggle (Default -> CurrentValue)
    def replace_addtoggle(match):
        prefix = match.group(1)
        content = match.group(2)
        # Replace "Default" with "CurrentValue" inside the content
        new_content = re.sub(r'Default\s*=', 'CurrentValue =', content)
        return f'{prefix}:CreateToggle({{{new_content}}})'
    text = re.sub(r'(\w+):AddToggle\(\{([\s\S]*?)\}\)', replace_addtoggle, text)

    # 8. Convert Tab:AddSlider to Tab:CreateSlider
    def replace_addslider(match):
        prefix = match.group(1)
        content = match.group(2)
        # Separate Callback for safe parsing
        callback_idx = content.find('Callback')
        callback_str = ""
        pre_content = content
        if callback_idx != -1:
            callback_str = content[callback_idx:]
            callback_str = callback_str.rstrip().rstrip(',')
            pre_content = content[:callback_idx].rstrip().rstrip(',')
        # Extract slider fields
        name_match = re.search(r'Name\s*=\s*(["\'].*?["\'])', pre_content)
        min_match = re.search(r'Min\s*=\s*([-\d.]+)', pre_content)
        max_match = re.search(r'Max\s*=\s*([-\d.]+)', pre_content)
        default_match = re.search(r'Default\s*=\s*([-\d.]+)', pre_content)
        inc_match = re.search(r'Increment\s*=\s*([-\d.]+)', pre_content)
        suffix_match = re.search(r'ValueName\s*=\s*(["\'].*?["\'])', pre_content)
        name_val = name_match.group(1) if name_match else '"Slider"'
        min_val = min_match.group(1) if min_match else '0'
        max_val = max_match.group(1) if max_match else '0'
        default_val = default_match.group(1) if default_match else min_val
        inc_val = inc_match.group(1) if inc_match else None
        suffix_val = suffix_match.group(1) if suffix_match else None
        fields = [
            f'Name = {name_val}',
            f'Range = {{{min_val}, {max_val}}}',
            f'CurrentValue = {default_val}'
        ]
        if inc_val:
            fields.append(f'Increment = {inc_val}')
        if suffix_val:
            fields.append(f'Suffix = {suffix_val}')
        if callback_str:
            fields.append(callback_str)
        return f'{prefix}:CreateSlider({{{", ".join(fields)}}})'
    text = re.sub(r'(\w+):AddSlider\(\{([\s\S]*?)\}\)', replace_addslider, text)

    # 9. Convert Tab:AddTextbox to Tab:CreateInput
    def replace_addtextbox(match):
        prefix = match.group(1)
        content = match.group(2)
        callback_idx = content.find('Callback')
        callback_str = ""
        pre_content = content
        if callback_idx != -1:
            callback_str = content[callback_idx:]
            callback_str = callback_str.rstrip().rstrip(',')
            pre_content = content[:callback_idx].rstrip().rstrip(',')
        name_match = re.search(r'Name\s*=\s*(["\'].*?["\'])', pre_content)
        default_match = re.search(r'Default\s*=\s*(["\'].*?["\'])', pre_content)
        disappear_match = re.search(r'TextDisappear\s*=\s*(true|false)', pre_content)
        name_val = name_match.group(1) if name_match else '"Textbox"'
        default_val = default_match.group(1) if default_match else '""'
        remove_val = 'true' if disappear_match and disappear_match.group(1) == 'true' else 'false'
        # Create a placeholder text to avoid missing placeholder error
        placeholder_text = "Enter text"
        if name_val[0] in ('"', "'"):
            name_str = name_val[1:-1]
            if name_str:
                placeholder_text = f"Enter {name_str}"
        placeholder_val = f'"{placeholder_text}"'
        fields = [
            f'Name = {name_val}',
            f'CurrentValue = {default_val}',
            f'PlaceholderText = {placeholder_val}',
            f'RemoveTextAfterFocusLost = {remove_val}'
        ]
        if callback_str:
            fields.append(callback_str)
        return f'{prefix}:CreateInput({{{", ".join(fields)}}})'
    text = re.sub(r'(\w+):AddTextbox\(\{([\s\S]*?)\}\)', replace_addtextbox, text)

    # 10. Convert Tab:AddColorpicker to Tab:CreateColorPicker (Default -> Color)
    def replace_addcolorpicker(match):
        prefix = match.group(1)
        content = match.group(2)
        # Replace "Default" with "Color"
        new_content = re.sub(r'Default\s*=', 'Color =', content)
        return f'{prefix}:CreateColorPicker({{{new_content}}})'
    text = re.sub(r'(\w+):AddColorpicker\(\{([\s\S]*?)\}\)', replace_addcolorpicker, text)

    # 11. Convert Tab:AddDropdown to Tab:CreateDropdown
    def replace_adddropdown(match):
        prefix = match.group(1)
        content = match.group(2)
        callback_idx = content.find('Callback')
        callback_str = ""
        pre_content = content
        if callback_idx != -1:
            callback_str = content[callback_idx:]
            callback_str = callback_str.rstrip().rstrip(',')
            pre_content = content[:callback_idx].rstrip().rstrip(',')
        name_match = re.search(r'Name\s*=\s*(["\'].*?["\'])', pre_content)
        options_match = re.search(r'Options\s*=\s*\{([^}]*)\}', pre_content)
        default_match = re.search(r'Default\s*=\s*(["\'].*?["\']|\w+)', pre_content)
        name_val = name_match.group(1) if name_match else '"Dropdown"'
        options_str = f'Options = {{{options_match.group(1)}}}' if options_match else 'Options = {}'
        # Determine CurrentOption (Rayfield expects a table of selected option(s))
        current_option_str = None
        if default_match:
            default_raw = default_match.group(1)
            if default_raw[0] in ('"', "'"):
                # Keep string inside quotes
                inner = default_raw[1:-1]
                current_option_str = f'CurrentOption = {{ "{inner}" }}'
            else:
                # Unquoted default (number or word)
                if default_raw.isdigit():
                    current_option_str = f'CurrentOption = {{ {default_raw} }}'
                else:
                    current_option_str = f'CurrentOption = {{ "{default_raw}" }}'
        else:
            # If no default, select first option if available
            if options_match:
                first_opt = options_match.group(1).split(',')[0].strip()
                if first_opt:
                    if first_opt[0] in ('"', "'"):
                        current_option_str = f'CurrentOption = {{ {first_opt} }}'
                    else:
                        current_option_str = f'CurrentOption = {{ {first_opt} }}'
        # Assemble fields
        fields = [f'Name = {name_val}', options_str]
        if current_option_str:
            fields.append(current_option_str)
        # (MultipleOptions default false, no need to include)
        if callback_str:
            fields.append(callback_str)
        return f'{prefix}:CreateDropdown({{{", ".join(fields)}}})'
    text = re.sub(r'(\w+):AddDropdown\(\{([\s\S]*?)\}\)', replace_adddropdown, text)

    # 12. Convert Tab:AddBind to Tab:CreateKeybind
    def replace_addbind(match):
        prefix = match.group(1)
        content = match.group(2)
        callback_idx = content.find('Callback')
        callback_str = ""
        pre_content = content
        if callback_idx != -1:
            callback_str = content[callback_idx:]
            callback_str = callback_str.rstrip().rstrip(',')
            pre_content = content[:callback_idx].rstrip().rstrip(',')
        name_match = re.search(r'Name\s*=\s*(["\'].*?["\'])', pre_content)
        default_match = re.search(r'Default\s*=\s*Enum\.KeyCode\.(\w+)', pre_content)
        hold_match = re.search(r'Hold\s*=\s*(true|false)', pre_content)
        name_val = name_match.group(1) if name_match else '"Keybind"'
        key_name = default_match.group(1) if default_match else ""
        current_key_val = f'"{key_name}"' if key_name else '""'
        hold_val = hold_match.group(1) if hold_match else 'false'
        fields = [
            f'Name = {name_val}',
            f'CurrentKeybind = {current_key_val}',
            f'HoldToInteract = {hold_val}'
        ]
        if callback_str:
            fields.append(callback_str)
        return f'{prefix}:CreateKeybind({{{", ".join(fields)}}})'
    text = re.sub(r'(\w+):AddBind\(\{([\s\S]*?)\}\)', replace_addbind, text)

    # 13. Replacing Notifications
    def replace_notification(match):
        content = match.group(1)

        # 1) Title: capture matching quotes and inner text
        m = re.search(r'Name\s*=\s*([\'"])(.*?)\1', content, re.DOTALL)
        inner_title = m.group(2) if m else ""
        escaped_title = inner_title.replace('"', '\\"')
        title_val = f'"{escaped_title}"'

        # 2) Content
        m = re.search(r'Content\s*=\s*([\'"])(.*?)\1', content, re.DOTALL)
        inner_content = m.group(2) if m else ""
        escaped_content = inner_content.replace('"', '\\"')
        content_val = f'"{escaped_content}"'

        # 3) Image (either "string" or numeric)
        image_field = None
        m = re.search(r'Image\s*=\s*([\'"])(.*?)\1|Image\s*=\s*(\d+)', content)
        if m:
            if m.group(2) is not None:
                raw_icon = m.group(2)
                if raw_icon.startswith("rbxassetid://"):
                    image_field = f'Image = {raw_icon.split("://",1)[1]}'
                else:
                    image_field = f'Image = "{raw_icon}"'
            elif m.group(3):
                image_field = f'Image = {m.group(3)}'

        # 4) Duration (was Time in Orion)
        duration_field = None
        m = re.search(r'Time\s*=\s*([0-9.]+)', content)
        if m:
            duration_field = f'Duration = {m.group(1)}'

        # 5) Assemble fields
        fields = [
            f'Title = {title_val}',
            f'Content = {content_val}'
        ]
        if image_field:
            fields.append(image_field)
        if duration_field:
            fields.append(duration_field)

        # 6) Return final Rayfield call
        return f'Rayfield:Notify({{{", ".join(fields)}}})'

    # And then hook it up with:
    text = re.sub(r'\w+:MakeNotification\(\{([\s\S]*?)\}\)', replace_notification, text)


    # 14. Replace OrionLib:Init() with Rayfield:LoadConfiguration() if config saving enabled, otherwise remove
    def replace_init(match):
        return 'Rayfield:LoadConfiguration()' if config_enabled else ''
    text = re.sub(r'\w+:Init\(\)', replace_init, text)

    # 15. Replace OrionLib:Destroy() with Rayfield:Destroy()
    text = re.sub(r'(?:getgenv\(\)\.)?[Oo]rion(?:Lib)?\s*:\s*Destroy\(\)', 'Rayfield:Destroy()', text)

    # 16. Convert any remaining rbxassetid:// occurrences to plain asset ID
    text = re.sub(r'"rbxassetid://(\d+)"', r'\1', text)

    # 17. Convert Tab:AddLabel("Text") to Tab:CreateLabel("Text", 0, Color3.fromRGB(255, 255, 255), false)
    def replace_addlabel(match):
        prefix = match.group(1)
        label_text = match.group(2).strip()
        return f'{prefix}:CreateLabel({label_text}, 0, Color3.fromRGB(255, 255, 255), false)'
    
    text = re.sub(r'(\w+):AddLabel\(\s*(["\'].*?["\'])\s*\)', replace_addlabel, text)


    return text




if __name__ == "__main__":
    with open('orion_script.lua', 'r', encoding='utf-8') as infile:
        orion_script = infile.read()

    rayfield_script = convert_orion_to_rayfield(orion_script)

    with open('rayfield_script.lua', 'w', encoding='utf-8') as outfile:
        outfile.write(rayfield_script)
