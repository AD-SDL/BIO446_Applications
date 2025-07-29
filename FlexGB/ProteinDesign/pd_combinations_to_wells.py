#!/usr/bin/env python3

import itertools

class CombinationProcessor:
    """A class to process combinatorial mixing configurations."""

    def __init__(self):
        """Initialize configuration and parts dictionaries."""
        self.config = {
            # Combinatorial mixing
            'combinations': [[2, 18], [3, 19], [4, 20], [5, 21]],  # 1-indexed source well numbers
        }
        self.parts = {
            # 1-indexed source well numbers for wells containing plasmids for Gibson Assembly
            0: "1-indexed",
            1: "p53_P1F0",
            2: "pJL-1_P1F0",
            3: "P1F1",
            4: "P1F2",
            5: "p53_P1F3",
            6: "pJL-1_P1F3",
            9: "p53_P5F0",
            10: "pJL-1_P5F0",
            11: "P5F1",
            12: "P5F2",
            13: "p53_P5F3",
            14: "pJL-1_P5F3",
            17: "p53_P6F0",
            18: "pJL-1_P6F0",
            19: "P6F1",
            20: "P6F2",
            21: "p53_P6F3",
            22: "pJL-1_P6F3"
        }

    def calculate_total_combinations(self, combinations):
        """Calculate total number of combinations without generating them."""
        try:
            total = 1
            for sublist in combinations:
                if not isinstance(sublist, list):
                    raise ValueError("Each combination must be a list")
                total *= len(sublist)
            return total
        except Exception as e:
            raise ValueError(f"Error calculating total combinations: {e}")

    def generate_all_combinations(self, combinations):
        """Generate all possible combinations from the jagged array."""
        try:
            return list(itertools.product(*combinations))
        except Exception as e:
            raise ValueError(f"Error generating combinations: {e}")

    def print_combinations(self):
        """Display combinations from config and parts."""
        try:
            combinations = self.config.get('combinations', [])
            if not combinations:
                raise ValueError("No combinations found in config")

            # Calculate total combinations before generating them
            total_combinations = self.calculate_total_combinations(combinations)
            print(f"Total combinations: {total_combinations}")

            # Generate all possible combinations
            all_combinations = self.generate_all_combinations(combinations)

            # Print combinations with part names
            print(f"Generated {len(all_combinations)} combinations:")
            for i, combo in enumerate(all_combinations, 1):
                # Map well numbers to part names, handling missing keys
                part_names = []
                for well in combo:
                    if well in self.parts:
                        part_names.append(f"{well}\t{self.parts[well]}")
                    else:
                        part_names.append(f"{well}\tUnknown")
                sources = '\t'.join(part_names)
                print(f"DestinationWell\t{i}\tSources\t{sources}")
            return True
        except Exception as e:
            print(f"Error in print_combinations: {e}")
            return False

    def write_combinations_to_file(self, filename="combinations.tsv"):
        """Write combinations to a tab-delimited file."""
        try:
            combinations = self.config.get('combinations', [])
            if not combinations:
                raise ValueError("No combinations found in config")

            # Generate all possible combinations
            all_combinations = self.generate_all_combinations(combinations)

            # Write to file
            with open(filename, 'w', encoding='utf-8') as f:
                # Write header
                f.write(f"DestinationWell\tNumber\tSources\n")
                # Write combinations
                for i, combo in enumerate(all_combinations, 1):
                    part_names = []
                    for well in combo:
                        if well in self.parts:
                            part_names.append(f"{well}\t{self.parts[well]}")
                        else:
                            part_names.append(f"{well}\tUnknown")
                    sources = '\t'.join(part_names)
                    f.write(f"DestinationWell\t{i}\tSources\t{sources}\n")
            print(f"Combinations written to {filename}")
            return True
        except Exception as e:
            print(f"Error writing to file: {e}")
            return False

    def run(self):
        """Main method to execute the program's logic."""
        try:
            # Print combinations to console
            print_success = self.print_combinations()
            # Write combinations to file
            write_success = self.write_combinations_to_file()
            return print_success and write_success
        except Exception as e:
            print(f"Error in run: {e}")
            return False

def main():
    """Main entry point of the program."""
    try:
        # Initialize the processor
        processor = CombinationProcessor()

        # Run the main logic
        success = processor.run()

        # Check if execution was successful
        if success:
            print("Program executed successfully.")
        else:
            print("Program failed to execute.")
        return 0
    except Exception as e:
        print(f"Error in main: {e}")
        return 1

if __name__ == "__main__":
    # Execute the main function and exit with appropriate status code
    exit_code = main()
    exit(exit_code)