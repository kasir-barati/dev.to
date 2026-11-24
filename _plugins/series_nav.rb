module SeriesNav
  class Generator < Jekyll::Generator
    safe true

    def generate(site)
      by_series = site.pages.select { |p| p.data["series"] }.group_by { |p| p.data["series"] }

      by_series.each_with_index do |(name, pages), i|
        pages.each { |p| p.data["parent"] = name }

        parent = Jekyll::PageWithoutAFile.new(site, site.source, "series", "#{Jekyll::Utils.slugify(name)}.md")
        parent.data.merge!("title" => name, "has_children" => true, "nav_order" => i + 2, "layout" => "default")
        parent.content = "# #{name}\n"
        site.pages << parent
      end
    end
  end
end
