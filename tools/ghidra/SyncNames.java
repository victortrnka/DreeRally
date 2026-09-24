// Applies function names from a TSV file (address<TAB>name) to the current program.
// Headless args: <names.tsv>
//@category DreeRally
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.SourceType;
import java.nio.file.Files;
import java.nio.file.Paths;

public class SyncNames extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 1) {
            printerr("usage: SyncNames.java <names.tsv>");
            return;
        }
        int renamed = 0, unchanged = 0, missing = 0, failed = 0;
        for (String line : Files.readAllLines(Paths.get(args[0]))) {
            if (line.isEmpty()) {
                continue;
            }
            String[] parts = line.split("\t");
            Function function = getFunctionAt(toAddr(Long.parseLong(parts[0], 16)));
            if (function == null) {
                println("NO FUNCTION at " + parts[0] + " for " + parts[1]);
                missing++;
            } else if (function.getName().equals(parts[1])) {
                unchanged++;
            } else {
                try {
                    function.setName(parts[1], SourceType.USER_DEFINED);
                    renamed++;
                } catch (Exception e) {
                    println("RENAME FAILED at " + parts[0] + " to " + parts[1] + ": " + e.getMessage());
                    failed++;
                }
            }
        }
        println(String.format("SUMMARY %d renamed, %d unchanged, %d without function, %d failed",
                renamed, unchanged, missing, failed));
    }
}
