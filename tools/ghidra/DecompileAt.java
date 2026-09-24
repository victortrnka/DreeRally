// Writes Ghidra's C decompilation of the function containing an address to a file.
// Headless args: <address, e.g. 0x415710> <output file>
//@category DreeRally
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import java.nio.file.Files;
import java.nio.file.Paths;

public class DecompileAt extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 2) {
            printerr("usage: DecompileAt.java <address> <output file>");
            return;
        }
        long offset = Long.parseLong(args[0].replaceFirst("(?i)^0x", ""), 16);
        Function function = getFunctionContaining(toAddr(offset));
        if (function == null) {
            println("NO FUNCTION contains " + args[0]);
            return;
        }
        DecompInterface decompiler = new DecompInterface();
        try {
            decompiler.openProgram(currentProgram);
            DecompileResults results = decompiler.decompileFunction(function, 120, monitor);
            if (!results.decompileCompleted()) {
                println("DECOMPILE FAILED: " + results.getErrorMessage());
                return;
            }
            Files.writeString(Paths.get(args[1]), results.getDecompiledFunction().getC());
        } finally {
            decompiler.dispose();
        }
    }
}
