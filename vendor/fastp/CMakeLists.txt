cmake_minimum_required(VERSION 3.10)
project(fastp LANGUAGES CXX)

# 设置默认构建类型
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE "Release" CACHE STRING "Build type" FORCE)
endif()

# 设置 C++ 标准
set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# 目录结构
set(DIR_INC ${CMAKE_CURRENT_SOURCE_DIR}/inc)
set(DIR_SRC ${CMAKE_CURRENT_SOURCE_DIR}/src)
set(DIR_COMPAT ${CMAKE_CURRENT_SOURCE_DIR}/compat)
set(DIR_OBJ ${CMAKE_CURRENT_BINARY_DIR}/obj)

# ================================================
# 1. 设置库路径
# ================================================
set(ISAL_ROOT "E:/Codes/isa-l" CACHE PATH "Path to ISA-L root directory")
set(DEFLATE_ROOT "E:/Codes/libdeflate" CACHE PATH "Path to libdeflate root directory")

message(STATUS "ISA-L root: ${ISAL_ROOT}")
message(STATUS "libdeflate root: ${DEFLATE_ROOT}")

# ================================================
# 2. 查找库文件
# ================================================
# 查找ISA-L库文件
find_library(ISAL_LIBRARY
    NAMES 
        isa-l
        isal
        isal_static
        libisal
    PATHS 
        "${ISAL_ROOT}"
        "${ISAL_ROOT}/out/build/x64-Debug"
        "${ISAL_ROOT}/out/build/x64-Release"
        "${ISAL_ROOT}/build"
        "${ISAL_ROOT}/lib"
    NO_DEFAULT_PATH
)

# 查找libdeflate库文件
find_library(DEFLATE_LIBRARY
    NAMES 
        deflatestatic
        libdeflatestatic
        libdeflate_static
        libdeflate
    PATHS 
        "${DEFLATE_ROOT}/out/build/x64-Debug"
        "${DEFLATE_ROOT}/out/build/x64-Release"
        "${DEFLATE_ROOT}/build"
        "${DEFLATE_ROOT}/lib"
    NO_DEFAULT_PATH
)

# 如果没找到，尝试递归搜索
if(NOT ISAL_LIBRARY)
    file(GLOB_RECURSE ISAL_LIB_CANDIDATES "${ISAL_ROOT}/*.lib")
    if(ISAL_LIB_CANDIDATES)
        list(GET ISAL_LIB_CANDIDATES 0 ISAL_LIBRARY)
        message(STATUS "Found ISA-L library (via glob): ${ISAL_LIBRARY}")
    endif()
endif()

if(NOT DEFLATE_LIBRARY)
    file(GLOB_RECURSE DEFLATE_LIB_CANDIDATES "${DEFLATE_ROOT}/*.lib")
    if(DEFLATE_LIB_CANDIDATES)
        list(GET DEFLATE_LIB_CANDIDATES 0 DEFLATE_LIBRARY)
        message(STATUS "Found libdeflate library (via glob): ${DEFLATE_LIBRARY}")
    endif()
endif()

if(ISAL_LIBRARY AND EXISTS "${ISAL_LIBRARY}")
    message(STATUS "Found ISA-L library: ${ISAL_LIBRARY}")
else()
    message(FATAL_ERROR "ISA-L library not found. Searched in: ${ISAL_ROOT}")
endif()

if(DEFLATE_LIBRARY AND EXISTS "${DEFLATE_LIBRARY}")
    message(STATUS "Found libdeflate library: ${DEFLATE_LIBRARY}")
else()
    message(FATAL_ERROR "libdeflate library not found. Searched in: ${DEFLATE_ROOT}")
endif()

# ================================================
# 3. 查找头文件
# ================================================
find_path(ISAL_INCLUDE_DIR
    NAMES isa-l.h
    PATHS 
        "${ISAL_ROOT}/include"
        "${ISAL_ROOT}"
    NO_DEFAULT_PATH
)

find_path(DEFLATE_INCLUDE_DIR
    NAMES libdeflate.h
    PATHS 
        "${DEFLATE_ROOT}"
        "${DEFLATE_ROOT}/include"
    NO_DEFAULT_PATH
)

if(ISAL_INCLUDE_DIR)
    message(STATUS "ISA-L include directory: ${ISAL_INCLUDE_DIR}")
else()
    message(FATAL_ERROR "ISA-L include directory not found")
endif()

if(DEFLATE_INCLUDE_DIR)
    message(STATUS "libdeflate include directory: ${DEFLATE_INCLUDE_DIR}")
else()
    message(FATAL_ERROR "libdeflate include directory not found")
endif()

# 可执行文件输出路径
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/bin)

# 查找所有源文件
file(GLOB SRC_FILES 
    "${DIR_SRC}/*.cpp"
)
list(FILTER SRC_FILES EXCLUDE REGEX ".*/src/(cxxabi|unistd)\\.cpp$")

# 添加兼容层源文件
file(GLOB COMPAT_FILES "${DIR_COMPAT}/*.cpp")

# 如果是Windows，创建cxa_demangle.cpp
if(WIN32)
    set(CXA_DEMANGLE_FILE "${DIR_COMPAT}/cxa_demangle.cpp")
    if(NOT EXISTS "${CXA_DEMANGLE_FILE}")
        file(WRITE "${CXA_DEMANGLE_FILE}" 
"#ifdef _WIN32
#include <windows.h>
#include <dbghelp.h>
#include <cstdlib>
#include <cstring>
#include <memory>

#pragma comment(lib, \"dbghelp.lib\")

extern \"C\" char* __cxa_demangle(const char* mangled_name,
                                char* output_buffer,
                                size_t* length,
                                int* status) {
    if (!mangled_name) {
        if (status) *status = -1;
        return nullptr;
    }
    
    char* result = nullptr;
    
    if (output_buffer) {
        DWORD ret = UnDecorateSymbolName(mangled_name, output_buffer, (DWORD)*length, UNDNAME_COMPLETE);
        if (ret > 0) {
            result = output_buffer;
            if (status) *status = 0;
        } else {
            if (status) *status = -1;
        }
    } else {
        DWORD needed = UnDecorateSymbolName(mangled_name, nullptr, 0, UNDNAME_COMPLETE);
        if (needed > 0) {
            result = static_cast<char*>(malloc(needed + 1));
            if (result) {
                DWORD ret = UnDecorateSymbolName(mangled_name, result, needed, UNDNAME_COMPLETE);
                if (ret > 0) {
                    if (length) *length = needed;
                    if (status) *status = 0;
                } else {
                    free(result);
                    result = nullptr;
                    if (status) *status = -1;
                }
            } else {
                if (status) *status = -1;
            }
        } else {
            size_t len = strlen(mangled_name);
            result = static_cast<char*>(malloc(len + 1));
            if (result) {
                strcpy_s(result, len + 1, mangled_name);
                if (length) *length = len;
                if (status) *status = 0;
            } else {
                if (status) *status = -1;
            }
        }
    }
    
    return result;
}

namespace abi {
    extern \"C\" char* __cxa_demangle(const char* mangled_name,
                                    char* output_buffer,
                                    size_t* length,
                                    int* status) {
        return ::_cxa_demangle(mangled_name, output_buffer, length, status);
    }
}
#endif
")
    endif()
    list(APPEND COMPAT_FILES "${CXA_DEMANGLE_FILE}")
endif()

# 创建可执行目标
add_executable(${PROJECT_NAME} ${SRC_FILES} ${COMPAT_FILES})

# ================================================
# 4. 设置包含目录
# ================================================
target_include_directories(${PROJECT_NAME} PRIVATE 
    ${DIR_INC} 
    ${DIR_COMPAT}
    ${ISAL_INCLUDE_DIR}
    ${DEFLATE_INCLUDE_DIR}
)

# ================================================
# 5. 创建导入目标
# ================================================
add_library(isal_imported STATIC IMPORTED)
set_target_properties(isal_imported PROPERTIES
    IMPORTED_LOCATION "${ISAL_LIBRARY}"
    INTERFACE_INCLUDE_DIRECTORIES "${ISAL_INCLUDE_DIR}"
)

add_library(libdeflate_imported STATIC IMPORTED)
set_target_properties(libdeflate_imported PROPERTIES
    IMPORTED_LOCATION "${DEFLATE_LIBRARY}"
    INTERFACE_INCLUDE_DIRECTORIES "${DEFLATE_INCLUDE_DIR}"
)

# ================================================
# 6. Windows 特定设置
# ================================================
if(WIN32)
    add_definitions(-D_CRT_SECURE_NO_WARNINGS)
    add_definitions(-D_CRT_NONSTDC_NO_WARNINGS)
    add_definitions(-DNOMINMAX)
    add_definitions(-DWIN32_LEAN_AND_MEAN)
    add_definitions(-DWIN32)
    
    # 设置 Windows SDK 版本
    set(CMAKE_VS_WINDOWS_TARGET_PLATFORM_VERSION "10.0.26100.0" CACHE STRING "Windows SDK Version")
    
    # 禁用特定警告
    add_compile_options(/wd4068)  # 未知的 pragma
    add_compile_options(/wd4819)  # 代码页问题
    
    # Windows 特定编译选项
    target_compile_options(${PROJECT_NAME} PRIVATE
        /W3           # 警告级别
        /MP           # 多处理器编译
        /EHsc         # 异常处理
    )
    
    if(CMAKE_BUILD_TYPE STREQUAL "Release")
        target_compile_options(${PROJECT_NAME} PRIVATE
            /O2        # 优化
            /Ob2       # 内联扩展
        )
    else()
        target_compile_options(${PROJECT_NAME} PRIVATE
            /Zi        # 调试信息
            /Od        # 禁用优化
        )
    endif()
    
    # 禁用更多MSVC警告
    target_compile_options(${PROJECT_NAME} PRIVATE
        /wd4996  # POSIX 名称被弃用
        /wd4273  # DLL 链接不一致
        /wd4005  # 宏重定义
        /wd4267  # size_t 到 int 转换
    )
endif()

# ================================================
# 7. 链接库
# ================================================
find_package(Threads REQUIRED)

# 链接所有库
target_link_libraries(${PROJECT_NAME} PRIVATE
    Threads::Threads
    ws2_32
    dbghelp
    psapi
    isal_imported
    libdeflate_imported
)

# ================================================
# 8. 其他设置
# ================================================
# 添加静态链接选项
option(BUILD_STATIC "Build with static linking" OFF)

if(BUILD_STATIC)
    if(MSVC)
        set_target_properties(${PROJECT_NAME} PROPERTIES
            LINK_FLAGS "/NODEFAULTLIB:msvcrt /MT"
        )
    else()
        target_link_options(${PROJECT_NAME} PRIVATE -static -Wl,--no-as-needed -pthread)
    endif()
endif()

# 安装目标
install(TARGETS ${PROJECT_NAME}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
    BUNDLE DESTINATION ${CMAKE_INSTALL_BINDIR}
)

# 支持生成 Visual Studio 解决方案的选项
if(MSVC)
    if(CMAKE_BUILD_TYPE STREQUAL "Release")
        set_target_properties(${PROJECT_NAME} PROPERTIES
            MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>"
        )
    else()
        set_target_properties(${PROJECT_NAME} PROPERTIES
            MSVC_RUNTIME_LIBRARY "MultiThreadedDebug$<$<CONFIG:Release>:>"
        )
    endif()
endif()

# 显示构建信息
message(STATUS "========================================")
message(STATUS "Build type: ${CMAKE_BUILD_TYPE}")
message(STATUS "Source directory: ${DIR_SRC}")
message(STATUS "Include directory: ${DIR_INC}")
message(STATUS "Compat directory: ${DIR_COMPAT}")
message(STATUS "ISA-L library: ${ISAL_LIBRARY}")
message(STATUS "libdeflate library: ${DEFLATE_LIBRARY}")
if(BUILD_STATIC)
    message(STATUS "Building with static linking")
endif()
message(STATUS "========================================")