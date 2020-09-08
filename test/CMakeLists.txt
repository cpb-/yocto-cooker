project(ChefTest NONE)

cmake_minimum_required(VERSION 3.8)

find_package(Git REQUIRED)

set(TEST_REPO ${CMAKE_BINARY_DIR}/repo)

add_custom_target(GenerateSourceRepoDir
    COMMAND ${CMAKE_COMMAND} -E remove_directory ${TEST_REPO}
    COMMAND ${CMAKE_COMMAND} -E make_directory ${TEST_REPO})

add_custom_target(GenerateSourceRepo
    ALL
    COMMAND ${GIT_EXECUTABLE} init
    COMMAND touch file1.txt
    COMMAND ${GIT_EXECUTABLE} add file1.txt
    COMMAND ${GIT_EXECUTABLE} commit -m 'initial commit'
    DEPENDS GenerateSourceRepoDir
    WORKING_DIRECTORY ${TEST_REPO})

enable_testing()

macro(test path)
    add_test(NAME ${path}
        COMMAND ${CMAKE_CURRENT_SOURCE_DIR}/driver.sh
                    ${path}
                    ${CMAKE_CURRENT_SOURCE_DIR}/${path})
endmacro()

test(basic/no-subcommand)
test(basic/build)
test(basic/clean)
test(basic/generate)
test(basic/init)
test(basic/show)
test(basic/dry-run)
