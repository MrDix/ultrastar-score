cmake_minimum_required(VERSION 3.18)
project(ultrastar_score LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(pybind11 CONFIG REQUIRED)

pybind11_add_module(_ptakf
    src/ultrastar_score/pitch/ptakf.cpp
    src/ultrastar_score/pitch/bindings.cpp
)

target_include_directories(_ptakf PRIVATE src/ultrastar_score/pitch)

install(TARGETS _ptakf DESTINATION ultrastar_score/pitch)
