import os
import re
import glob

def parse_and_instrument(filepath, category, project, issue):
    with open(filepath, 'r') as f:
        content = f.read()

    # Change package to main
    content = re.sub(r'package\s+\w+', 'package main', content)

    # Clean up imports: add "os" and "runtime/trace"
    # Locate import block
    import_match = re.search(r'import\s*\((.*?)\)', content, re.DOTALL)
    if import_match:
        imports = import_match.group(1)
        # Add os and runtime/trace if not already there
        if '"os"' not in imports:
            imports += '\n\t"os"'
        if '"runtime/trace"' not in imports:
            imports += '\n\t"runtime/trace"'
        content = content.replace(import_match.group(0), f'import ({imports}\n)')
    else:
        # Single import or no import
        content = re.sub(r'import\s+"[^"]+"', 'import (\n\t"os"\n\t"runtime/trace"\n)', content)

    # Locate Test function
    test_func_match = re.search(r'func\s+Test\w+\s*\(\s*\w+\s+\*testing\.T\s*\)\s*\{(.*)', content, re.DOTALL)
    if not test_func_match:
        # Try without pointer/variable name
        test_func_match = re.search(r'func\s+Test\w+\s*\(\s*\*testing\.T\s*\)\s*\{(.*)', content, re.DOTALL)

    if test_func_match:
        body = test_func_match.group(1)
        
        # Replace the test function with main
        main_func = f"""func main() {{
	if tf := os.Getenv("WEAVE_TRACE_FILE"); tf != "" {{
		f, err := os.Create(tf)
		if err == nil {{
			if err := trace.Start(f); err == nil {{
				defer func() {{ trace.Stop(); f.Close() }}()
			}}
		}}
	}}
{body}"""
        # We need to replace from the test function declaration to the end of file
        # We can find the test function declaration
        decl_match = re.search(r'func\s+Test\w+\s*\([^)]*\)\s*\{', content)
        if decl_match:
            start_idx = decl_match.start()
            content = content[:start_idx] + main_func

    # Clean up any references to *testing.T inside if they exist (rare in simple kernels)
    content = re.sub(r't\s+\*testing\.T', '', content)
    
    # Guess concurrency pattern
    pattern = "channel"
    if "Mutex" in content or "RWMutex" in content or "Lock()" in content:
        pattern = "mutex"

    # Count goroutines
    go_count = len(re.findall(r'\bgo\b', content))

    metadata = f"""// WEAVE_META
// outcome: {category}
// concurrency_pattern: {pattern}
// goroutine_count: {go_count}
// expected_nondeterminism: medium
// description: Auto-extracted GoBench bug kernel {project}_{issue} ({category})

"""
    
    return metadata + content

def main():
    goker_path = "temp_repos/gobench/gobench/goker"
    dest_dir = "programs"
    os.makedirs(dest_dir, exist_ok=True)

    imported_count = 0
    for category in ["blocking", "nonblocking"]:
        cat_path = os.path.join(goker_path, category)
        for project in os.listdir(cat_path):
            proj_path = os.path.join(cat_path, project)
            if not os.path.isdir(proj_path):
                continue
            for issue in os.listdir(proj_path):
                issue_path = os.path.join(proj_path, issue)
                if not os.path.isdir(issue_path):
                    continue
                
                # Find the go file
                go_files = glob.glob(os.path.join(issue_path, "*.go"))
                for gf in go_files:
                    if gf.endswith("_test.go"):
                        out_filename = f"goker_{project}_{issue}.go"
                        out_filepath = os.path.join(dest_dir, out_filename)
                        
                        # Avoid overwriting already existing/manually-verified programs
                        if os.path.exists(out_filepath):
                            print(f"Skipping existing: {out_filename}")
                            continue

                        try:
                            instrumented_code = parse_and_instrument(gf, category, project, issue)
                            with open(out_filepath, 'w') as out_f:
                                out_f.write(instrumented_code)
                            print(f"Imported: {out_filename}")
                            imported_count += 1
                        except Exception as e:
                            print(f"Error parsing {gf}: {e}")

    print(f"\nSuccessfully imported {imported_count} new GoKer programs.")

if __name__ == "__main__":
    main()
