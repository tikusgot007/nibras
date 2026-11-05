/* Nibras launcher (D-60).
 *
 * Finds the USB root from its own location, verifies the volume is NTFS,
 * prepares the environment, and starts the Python application with no
 * console window.
 *
 * - NTFS is verified with GetVolumeInformationW. A non-NTFS volume shows
 *   a MessageBox with guidance and the launcher NEVER formats or
 *   converts the drive.
 * - Environment for the child process (D-12, D-07):
 *     PYTHONHOME=App\python
 *     PYTHONNOUSERSITE=1
 *     PYTHONDONTWRITEBYTECODE=1
 *     PYTHONPATH removed (the app package lives in site-packages)
 *     TEMP/TMP and Qt cache redirected to Temp\ on the USB stick
 * - Runs App\python\pythonw.exe -m nibras (no console).
 *
 * Build (on Windows, mingw-w64):
 *   x86_64-w64-mingw32-gcc -mwindows -O2 -o Nibras.exe nibras.c
 * See launcher/build_launcher.ps1.
 */

#define UNICODE
#define _UNICODE
#include <windows.h>
#include <stdio.h>

static void show_error(const wchar_t *message) {
    MessageBoxW(NULL, message, L"Nibras", MB_OK | MB_ICONERROR);
}

static int path_join(wchar_t *dest, size_t dest_chars, const wchar_t *a,
                     const wchar_t *b) {
    size_t la = wcslen(a);
    size_t lb = wcslen(b);
    if (la + 1 + lb + 1 > dest_chars) return 0;
    wcscpy_s(dest, dest_chars, a);
    if (la > 0 && dest[la - 1] != L'\\') {
        dest[la] = L'\\';
        dest[la + 1] = L'\0';
        la++;
    }
    wcscat_s(dest, dest_chars, b);
    return 1;
}

int WINAPI wWinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance,
                    PWSTR pCmdLine, int nCmdShow) {
    (void)hInstance; (void)hPrevInstance; (void)pCmdLine; (void)nCmdShow;

    wchar_t exe_path[MAX_PATH];
    if (!GetModuleFileNameW(NULL, exe_path, MAX_PATH)) {
        show_error(L"Tidak bisa menemukan lokasi Nibras.exe.");
        return 1;
    }
    /* USB root = folder containing Nibras.exe. */
    wchar_t *slash = wcsrchr(exe_path, L'\\');
    if (!slash) {
        show_error(L"Lokasi Nibras.exe tidak valid.");
        return 1;
    }
    *slash = L'\0';
    wchar_t root[MAX_PATH];
    wcscpy_s(root, MAX_PATH, exe_path);

    /* NTFS check (D-58): never format or convert. */
    wchar_t volume_root[MAX_PATH];
    if (!path_join(volume_root, MAX_PATH, root, L"")) {
        show_error(L"Path flashdisk terlalu panjang.");
        return 1;
    }
    wchar_t fs_name[MAX_PATH];
    if (!GetVolumeInformationW(volume_root, NULL, 0, NULL, NULL, NULL,
                              fs_name, MAX_PATH)) {
        show_error(L"Tidak bisa membaca informasi flashdisk.");
        return 1;
    }
    if (wcscmp(fs_name, L"NTFS") != 0) {
        wchar_t msg[512];
        swprintf_s(msg, 512,
            L"Flashdisk ini memakai sistem file %ls, bukan NTFS.\n\n"
            L"Nibras membutuhkan flashdisk NTFS agar data aman saat "
            L"flashdisk dicabut mendadak.\n\n"
            L"Salin dulu isi flashdisk ke tempat aman, lalu format "
            L"flashdisk ini sebagai NTFS di Windows (klik kanan drive > "
            L"Format > NTFS), kemudian pasang ulang Nibras.",
            fs_name);
        show_error(msg);
        return 1;
    }

    wchar_t app_python[MAX_PATH], temp_dir[MAX_PATH], qt_cache[MAX_PATH];
    wchar_t pythonw[MAX_PATH];
    if (!path_join(app_python, MAX_PATH, root, L"App\\python") ||
        !path_join(temp_dir, MAX_PATH, root, L"Temp") ||
        !path_join(pythonw, MAX_PATH, app_python, L"pythonw.exe")) {
        show_error(L"Path instalasi Nibras terlalu panjang.");
        return 1;
    }
    path_join(qt_cache, MAX_PATH, temp_dir, L"qt-cache");

    CreateDirectoryW(temp_dir, NULL);
    CreateDirectoryW(qt_cache, NULL);

    SetEnvironmentVariableW(L"PYTHONHOME", app_python);
    SetEnvironmentVariableW(L"PYTHONNOUSERSITE", L"1");
    SetEnvironmentVariableW(L"PYTHONDONTWRITEBYTECODE", L"1");
    SetEnvironmentVariableW(L"PYTHONPATH", NULL);
    SetEnvironmentVariableW(L"TEMP", temp_dir);
    SetEnvironmentVariableW(L"TMP", temp_dir);
    SetEnvironmentVariableW(L"QT_QPA_PLATFORM", L"windows");
    /* Qt cache + WebEngine-style caches stay on the stick (D-07). */
    SetEnvironmentVariableW(L"XDG_CACHE_HOME", qt_cache);

    wchar_t cmdline[MAX_PATH + 64];
    swprintf_s(cmdline, MAX_PATH + 64, L"\"%ls\" -m nibras", pythonw);

    STARTUPINFOW si;
    PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si));
    si.cb = sizeof(si);
    ZeroMemory(&pi, sizeof(pi));
    if (!CreateProcessW(NULL, cmdline, NULL, NULL, FALSE,
                       CREATE_NO_WINDOW, NULL, root, &si, &pi)) {
        wchar_t msg[512];
        swprintf_s(msg, 512,
            L"Tidak bisa menjalankan Python di flashdisk.\n\n"
            L"Pastikan folder App\\python\\pythonw.exe ada. "
            L"Coba pasang ulang Nibras dengan install_to_usb.ps1.");
        show_error(msg);
        return 1;
    }
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    return 0;
}
